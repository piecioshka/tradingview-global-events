#!/usr/bin/env python3
"""Auto-discovers data/events-*.md and injects generated sections into worldwide-events.pine."""

import re
import os
import glob

DATA_DIR  = "data"
PINE_FILE = "worldwide-events.pine"

PRIORITY_TO_COLOR = {
    "high":   ", COLOR_HIGH_PRIORITY",
    "medium": ", COLOR_MEDIUM_PRIORITY",
}


def discover_languages():
    """Returns sorted language codes from data/events-*.md, EN first if present."""
    files = sorted(glob.glob(os.path.join(DATA_DIR, "events-*.md")))
    langs = [os.path.basename(f).replace("events-", "").replace(".md", "").upper()
             for f in files]
    if "EN" in langs:
        langs.remove("EN")
        langs.insert(0, "EN")
    return langs


def parse_events(path):
    events = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("|") or line.startswith("| Date") or line.startswith("| ---"):
                continue
            parts = [p.strip() for p in line.strip("|").split("|")]
            if len(parts) < 3:
                continue
            date, desc, priority = parts[0], parts[1], parts[2]
            events[date] = (desc, priority)
    return events


def gen_lang_input(langs):
    options = '["' + '", "'.join(langs) + '"]'
    return f'lang                 = input.string("{langs[0]}", "Language", options={options}, group="Settings")'


def gen_lang_arrays(langs):
    lines = [f"var labels_{lang.lower()} = array.new_string()" for lang in langs]
    return "\n".join(lines)


def gen_new_event_func(langs):
    params = ", ".join(f"string l_{lang.lower()}" for lang in langs)
    pushes = "\n".join(f"    array.push(labels_{lang.lower()}, l_{lang.lower()})" for lang in langs)
    return (
        f"new_event(int t, {params}, color c = na) =>\n"
        f"    array.push(times, t)\n"
        f"{pushes}\n"
        f"    array.push(colors, na(c) ? COLOR_LOW_PRIORITY : c)"
    )


def gen_events_block(langs, lang_data):
    primary = lang_data[langs[0]]
    lines = []
    for date, (desc_primary, priority) in primary.items():
        descs = []
        for lang in langs:
            desc = lang_data.get(lang, {}).get(date, (desc_primary,))[0]
            descs.append(f'"{desc}"')
        color = PRIORITY_TO_COLOR.get(priority, "")
        lines.append(f'    new_event(timestamp("{date}"), {", ".join(descs)}{color})')
    return "\n".join(lines)


def gen_label_lookup(langs):
    # Nested ternary; last language is the fallback
    expr = f"array.get(labels_{langs[-1].lower()}, i)"
    for lang in reversed(langs[:-1]):
        expr = f'lang == "{lang}" ? array.get(labels_{lang.lower()}, i) : {expr}'
    return f"        l = {expr}"


def inject_section(content, marker, replacement):
    # Match both top-level and indented @end-generated tags
    pattern = rf"([ \t]*// @generated {re.escape(marker)}\n)(.*?)(\n[ \t]*// @end-generated)"
    m = re.search(rf"([ \t]*)// @generated {re.escape(marker)}", content)
    indent = m.group(1) if m else ""
    end_tag = f"\n{indent}// @end-generated"
    repl = rf"\g<1>{replacement}{end_tag}"
    return re.sub(pattern, repl, content, flags=re.DOTALL)


def inject_events(content, events_block):
    pattern = r"(if barstate\.isfirst\n)(.*?)(\n\nif barstate\.islast)"
    return re.sub(pattern, rf"\g<1>{events_block}\g<3>", content, flags=re.DOTALL)


def main():
    langs = discover_languages()
    print(f"Languages: {langs}")

    lang_data = {lang: parse_events(os.path.join(DATA_DIR, f"events-{lang.lower()}.md"))
                 for lang in langs}

    with open(PINE_FILE, encoding="utf-8") as f:
        content = f.read()

    content = inject_section(content, "lang-input",     gen_lang_input(langs))
    content = inject_section(content, "lang-arrays",    gen_lang_arrays(langs))
    content = inject_section(content, "new-event-func", gen_new_event_func(langs))
    content = inject_events(content,                    gen_events_block(langs, lang_data))
    content = inject_section(content, "label-lookup",   gen_label_lookup(langs))

    with open(PINE_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Updated {PINE_FILE}")


if __name__ == "__main__":
    main()
