#!/usr/bin/env python3
"""Publish reviewed posts and images, then remove this run's owned scratch files."""
import argparse
import json
from pathlib import Path
import re
import shutil
import tempfile

from PIL import Image

MARKER = ".github-treasure-work"


def finalize(posts, work_dir, output_dir):
    work_dir, output_dir = work_dir.resolve(), output_dir.resolve()
    if not (work_dir / MARKER).is_file():
        raise ValueError("Work directory is not owned by GitHub Treasure")
    if work_dir == output_dir or work_dir in output_dir.parents or output_dir in work_dir.parents:
        raise ValueError("Final output and work directory must be separate")
    if output_dir.exists():
        raise ValueError("Final output already exists; use a new directory")
    if not isinstance(posts, list) or not 5 <= len(posts) <= 6:
        raise ValueError("Expected 5 or 6 reviewed posts")
    report = json.loads((work_dir / "manifest.json").read_text(encoding="utf-8"))
    by_repo = {item["repo"]: item for item in report}
    prepared, seen = [], set()
    for number, post in enumerate(posts, 1):
        repo = post["repo"]
        if repo.lower() in seen or post.get("visually_reviewed") is not True:
            raise ValueError("Each project must be unique and visually reviewed")
        seen.add(repo.lower())
        item = by_repo[repo]
        image_path = Path(item["image_path"]).resolve()
        if image_path.parent != work_dir or item["status"] not in ("downloaded", "captured", "cached"):
            raise ValueError("Image is not a successful result inside this work directory")
        with Image.open(image_path) as picture:
            picture.verify()
        with Image.open(image_path) as picture:
            picture.load()
        text = post["text"].strip()
        lines = text.splitlines()
        if len(lines) < 2 or lines[-1] != f"🔗 https://github.com/{repo}":
            raise ValueError("Post must end with its own GitHub URL on a separate line")
        if not "".join(lines[:-1]).strip():
            raise ValueError("Post must include share text before its GitHub URL")
        prepared.append((number, text, image_path))
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    # Publish only after every entry validates. The temporary directory is always removed.
    with tempfile.TemporaryDirectory(prefix=".treasure-final-", dir=output_dir.parent) as temp:
        stage = Path(temp)
        (stage / "images").mkdir()
        blocks = []
        for number, text, image_path in prepared:
            filename = f"{number:02d}-{image_path.name}"
            shutil.copyfile(image_path, stage / "images" / filename)
            blocks.append(f"【帖子 {number}】\n{text}")
        (stage / "posts.txt").write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
        shutil.copytree(stage, output_dir)
    # Delete only files this collector created; leave unknown files and user inputs alone.
    owned = {work_dir / MARKER, work_dir / "manifest.json"}
    for cache in work_dir.glob("*.json"):
        try:
            saved = json.loads(cache.read_text(encoding="utf-8"))
            image_path = Path(saved["image_path"]).resolve()
            expected = re.escape(saved["repo"].replace("/", "--")) + r"-[0-9a-f]{16}"
            if (re.fullmatch(expected, cache.stem) and image_path.parent == work_dir
                    and image_path.stem == cache.stem):
                owned.update((cache, image_path))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    removed = 0
    for path in owned:
        if path.parent == work_dir and path.is_file() and not path.is_symlink():
            path.unlink()
            removed += 1
    if not any(work_dir.iterdir()):
        work_dir.rmdir()
    return {"output_dir": str(output_dir), "posts": len(prepared), "removed_work_files": removed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--posts", type=Path, required=True, help="JSON array of {repo, text, visually_reviewed: true}")
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = finalize(json.loads(args.posts.read_text(encoding="utf-8-sig")), args.work_dir, args.output_dir)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, str(exc) + "\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
