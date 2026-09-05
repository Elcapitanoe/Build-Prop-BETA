import os, glob, json, datetime

def main():
    metadata_files = sorted(glob.glob("new_modules/metadata-*.json"))
    if not metadata_files:
        print("No metadata files found.")
        return

    entries = []
    for f in metadata_files:
        with open(f, "r", encoding="utf-8") as jf:
            d = json.load(jf)
        dev = d.get("device_name", "")
        cname = d.get("codename", "")
        zname = d.get("zip_name", "")
        s256 = d.get("sha256", "")
        bdesc = d.get("build_desc", "")

        line = f"- **{dev} ({cname.capitalize()})**: `{zname}`\n  - SHA256: `{s256}`\n"
        if bdesc:
            line += f"  - Build: `{bdesc}`\n"
        entries.append(line)

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    block = f"## [{today}]\n" + "".join(entries) + "\n"

    changelog_path = "target_repo/CHANGELOG.md"
    if not os.path.exists(changelog_path):
        with open(changelog_path, "w", encoding="utf-8") as cf:
            cf.write(f"# Changelog\n\n{block}")
        return

    with open(changelog_path, "r", encoding="utf-8") as cf:
        body = cf.read()

    if f"## [{today}]" in body:
        print("Today's changelog block already exists, skipping.")
        return

    if "\n## " in body:
        idx = body.index("\n## ")
        body = body[:idx+1] + block + body[idx+1:]
    else:
        body = body.rstrip() + "\n\n" + block

    with open(changelog_path, "w", encoding="utf-8") as cf:
        cf.write(body)
    print("CHANGELOG.md updated successfully.")

if __name__ == "__main__":
    main()
