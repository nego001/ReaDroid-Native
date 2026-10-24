"""Test one-shot recovery from emulator Pixel Launcher ANR without hiding app faults."""
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from tools import android_ui_smoke as smoke


def node(**attributes):
    return ET.Element("node", attributes)


class EmulatorLauncherRecoveryTests(unittest.TestCase):
    def test_regular_screen_is_not_modified(self):
        original = [node(package="com.readroid.app", **{"content-desc": "Seção Início, selecionada"})]
        with patch.object(smoke, "hierarchy", return_value=original), \
             patch.object(smoke, "tap") as tap:
            self.assertIs(smoke.visible_app_hierarchy(), original)
            tap.assert_not_called()

    def test_known_launcher_anr_dismissed_once_and_rechecks_app(self):
        overlay = [
            node(text="Pixel Launcher isn't responding", package="android"),
            node(package="android", bounds="[20,80][200,160]",
                 **{"resource-id": "android:id/aerr_close"}),
        ]
        restored = [node(package="com.readroid.app",
                         **{"content-desc": "Seção Início, selecionada"})]
        with patch.object(smoke, "hierarchy", side_effect=[overlay, restored]) as read, \
             patch.object(smoke, "tap") as tap:
            result = smoke.visible_app_hierarchy()
            self.assertIs(result, restored)
            self.assertEqual(read.call_count, 2)
            tap.assert_called_once_with(overlay[1])

    def test_app_anr_is_never_dismissed(self):
        for brand in ("NegrecoDroid", "NegrescoDroid"):
            with self.subTest(brand=brand):
                overlay = [node(text=brand + " isn't responding", package="android")]
                with patch.object(smoke, "hierarchy", return_value=overlay), \
                     patch.object(smoke, "tap") as tap:
                    with self.assertRaisesRegex(AssertionError, "NegrecoDroid ANR"):
                        smoke.visible_app_hierarchy()
                    tap.assert_not_called()

    def test_unrelated_dialog_is_never_dismissed(self):
        overlay = [
            node(text="Camera isn't responding", package="android"),
            node(package="android", **{"resource-id": "android:id/aerr_close"}),
        ]
        with patch.object(smoke, "hierarchy", return_value=overlay), \
             patch.object(smoke, "tap") as tap:
            self.assertIs(smoke.visible_app_hierarchy(), overlay)
            tap.assert_not_called()

    def test_launcher_overlay_without_close_button_fails_closed(self):
        overlay = [node(text="Pixel Launcher isn't responding", package="android")]
        with patch.object(smoke, "hierarchy", return_value=overlay), \
             patch.object(smoke, "tap") as tap:
            with self.assertRaisesRegex(AssertionError, "unambiguous"):
                smoke.visible_app_hierarchy()
            tap.assert_not_called()

    def test_launcher_overlay_persists_only_one_attempt(self):
        overlay = [
            node(text="Pixel Launcher isn't responding", package="android"),
            node(package="android", **{"resource-id": "android:id/aerr_close"}),
        ]
        with patch.object(smoke, "hierarchy", side_effect=[overlay, overlay]), \
             patch.object(smoke, "tap") as tap:
            with self.assertRaisesRegex(AssertionError, "remains"):
                smoke.visible_app_hierarchy()
            tap.assert_called_once()


if __name__ == "__main__":
    unittest.main()
