"""Check final delivery validation and cleanup boundaries without network access."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "finalize_output.py"
SPEC = importlib.util.spec_from_file_location("finalize_output", SCRIPT)
finalizer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(finalizer)


class FinalizeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="treasure-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / "work"
        self.work.mkdir()
        (self.work / finalizer.MARKER).write_text("generated")
        self.output = self.root / "final"
        self.posts, report = [], []
        buffer = io.BytesIO()
        Image.new("RGB", (480, 270)).save(buffer, format="PNG")
        for i in range(6):
            repo = f"example/tool{i}"
            stem = f"example--tool{i}-0123456789abcdef"
            image = self.work / (stem + ".png")
            image.write_bytes(buffer.getvalue())
            item = {"repo": repo, "image_path": str(image), "status": "downloaded"}
            (self.work / (stem + ".json")).write_text(json.dumps(item))
            report.append(item)
            text = "资料太多，每次找文件都要翻半天！\n\n工具把散落的资料收进一个可搜索的界面，支持标签整理、内容检索和批量导出，日常查找更省事。\n\n经常整理工作资料、查阅历史文件的朋友可以试试，需要自行部署服务。\n\n🔗 https://github.com/" + repo
            self.posts.append({"repo": repo, "text": text, "visually_reviewed": True})
        (self.work / "manifest.json").write_text(json.dumps(report))

    def test_final_contains_only_posts_and_selected_images(self):
        result = finalizer.finalize(self.posts[:5], self.work, self.output)
        self.assertEqual(result["posts"], 5)
        self.assertEqual(sorted(p.name for p in self.output.iterdir()), ["images", "posts.txt"])
        self.assertEqual(len(list((self.output / "images").iterdir())), 5)
        self.assertFalse(self.work.exists())

    def test_unreviewed_image_publishes_nothing_and_preserves_work(self):
        self.posts[0]["visually_reviewed"] = False
        with self.assertRaisesRegex(ValueError, "visually reviewed"):
            finalizer.finalize(self.posts, self.work, self.output)
        self.assertFalse(self.output.exists())
        self.assertTrue((self.work / "manifest.json").is_file())

    def test_conversational_posts_keep_varied_layouts_and_lengths(self):
        bodies = [
            "兄弟们，复制过的链接被覆盖了，你们都怎么找回来？这个工具能搜索历史记录。",
            "手机和电脑传文件，你们用什么？\n\n两端装好就能在局域网互传。",
            "同一个问题怎么比较几个模型的回答？\n这个工作台支持多模型对话。\n\n云端模型需要自行配置。",
            "电子书格式太多怎么办？\n\n把书导入同一个书架。\n\n能高亮、记笔记。\n\n也能导出笔记。",
            "字幕和配音怎么一起处理？" + "可以按阶段校对字幕，再继续处理。" * 15,
            "旧笔记怎么连到新文章里？\n\n可以直接关联具体段落。",
        ]
        for post, body in zip(self.posts, bodies):
            post["text"] = body + f"\n\n🔗 https://github.com/{post['repo']}"
        finalizer.finalize(self.posts, self.work, self.output)
        delivered = (self.output / "posts.txt").read_text(encoding="utf-8")
        for post in self.posts:
            self.assertIn(post["text"], delivered)

    def test_missing_or_mismatched_repository_link_publishes_nothing(self):
        for text in (
            "兄弟们，你们平时怎么整理文件？",
            "兄弟们，你们平时怎么整理文件？\n🔗 https://github.com/example/wrong",
            "兄弟们，你们平时怎么整理文件？ 🔗 https://github.com/example/tool0",
        ):
            with self.subTest(text=text):
                self.posts[0]["text"] = text
                with self.assertRaisesRegex(ValueError, "own GitHub URL"):
                    finalizer.finalize(self.posts, self.work, self.output)
                self.assertFalse(self.output.exists())
                self.assertTrue((self.work / "manifest.json").is_file())

    def test_link_without_share_text_publishes_nothing(self):
        self.posts[0]["text"] = "\n\n🔗 https://github.com/example/tool0"
        with self.assertRaises(ValueError):
            finalizer.finalize(self.posts, self.work, self.output)
        self.assertFalse(self.output.exists())

    def test_unknown_files_and_original_inputs_are_preserved(self):
        note = self.work / "notes--original.png"
        note.write_text("user input")
        finalizer.finalize(self.posts, self.work, self.output)
        self.assertEqual(note.read_text(), "user input")

    def test_existing_delivery_is_not_overwritten(self):
        self.output.mkdir()
        (self.output / "keep.txt").write_text("original")
        with self.assertRaisesRegex(ValueError, "already exists"):
            finalizer.finalize(self.posts, self.work, self.output)
        self.assertEqual((self.output / "keep.txt").read_text(), "original")

    def test_external_image_is_rejected(self):
        manifest = self.work / "manifest.json"
        report = json.loads(manifest.read_text())
        report[0]["image_path"] = str(self.root / "original.png")
        manifest.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, "inside this work directory"):
            finalizer.finalize(self.posts, self.work, self.output)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
