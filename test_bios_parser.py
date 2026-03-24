"""
test_bios_parser.py
bios_parser 모듈의 단위 테스트.
"""

import json
import os
import tempfile
import unittest

from bios_parser import (
    _count_fields,
    _extract_field,
    _parse_field,
    _parse_section,
    load_json,
    parse_bios_json,
)

SAMPLE_BIOS = {
    "bios": {
        "version": "1.0.0",
        "manufacturer": "AMI",
        "product": "Test Board",
        "date": "2024-01-01",
        "sections": {
            "main": {
                "label": "Main",
                "fields": {
                    "bios_version": {
                        "label": "BIOS Version",
                        "value": "0602",
                        "type": "string",
                        "readonly": True,
                    },
                    "system_language": {
                        "label": "System Language",
                        "value": "English",
                        "type": "enum",
                        "options": ["English", "Korean"],
                        "readonly": False,
                    },
                },
            },
            "advanced": {
                "label": "Advanced",
                "fields": {
                    "cpu_configuration": {
                        "label": "CPU Configuration",
                        "type": "group",
                        "fields": {
                            "hyper_threading": {
                                "label": "Hyper-Threading",
                                "value": "Enabled",
                                "type": "enum",
                                "options": ["Enabled", "Disabled"],
                                "readonly": False,
                            },
                        },
                    },
                    "memory_slots": {
                        "label": "Memory Slots",
                        "type": "array",
                        "items": [
                            {"slot": "DIMM_A1", "status": "Populated", "size": "16384"},
                            {"slot": "DIMM_B1", "status": "Populated", "size": "16384"},
                        ],
                    },
                },
            },
            "monitor": {
                "label": "Monitor",
                "fields": {
                    "cpu_temperature": {
                        "label": "CPU Temperature",
                        "value": 42,
                        "type": "integer",
                        "unit": "°C",
                        "readonly": True,
                    },
                    "cpu_core_voltage": {
                        "label": "CPU Core Voltage",
                        "value": 1.25,
                        "type": "float",
                        "unit": "V",
                        "readonly": True,
                    },
                },
            },
        },
    }
}


class TestLoadJson(unittest.TestCase):
    def test_load_valid_json(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(SAMPLE_BIOS, f)
            tmp_path = f.name
        try:
            data = load_json(tmp_path)
            self.assertEqual(data["bios"]["manufacturer"], "AMI")
        finally:
            os.unlink(tmp_path)

    def test_load_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            load_json("/nonexistent/path/file.json")


class TestParseBiosJson(unittest.TestCase):
    def setUp(self):
        self.parsed = parse_bios_json(SAMPLE_BIOS)

    def test_meta_fields(self):
        meta = self.parsed["meta"]
        self.assertEqual(meta["version"], "1.0.0")
        self.assertEqual(meta["manufacturer"], "AMI")
        self.assertEqual(meta["product"], "Test Board")
        self.assertEqual(meta["date"], "2024-01-01")

    def test_sections_present(self):
        self.assertIn("main", self.parsed["sections"])
        self.assertIn("advanced", self.parsed["sections"])
        self.assertIn("monitor", self.parsed["sections"])

    def test_section_labels(self):
        self.assertEqual(self.parsed["sections"]["main"]["label"], "Main")
        self.assertEqual(self.parsed["sections"]["advanced"]["label"], "Advanced")

    def test_scalar_field_parsed(self):
        bios_version = self.parsed["sections"]["main"]["fields"]["bios_version"]
        self.assertEqual(bios_version["value"], "0602")
        self.assertEqual(bios_version["type"], "string")
        self.assertTrue(bios_version["readonly"])

    def test_enum_field_options(self):
        lang = self.parsed["sections"]["main"]["fields"]["system_language"]
        self.assertEqual(lang["value"], "English")
        self.assertIn("Korean", lang["options"])
        self.assertFalse(lang["readonly"])

    def test_group_field_parsed(self):
        cpu_config = self.parsed["sections"]["advanced"]["fields"]["cpu_configuration"]
        self.assertEqual(cpu_config["type"], "group")
        self.assertIn("hyper_threading", cpu_config["fields"])
        ht = cpu_config["fields"]["hyper_threading"]
        self.assertEqual(ht["value"], "Enabled")

    def test_array_field_parsed(self):
        slots = self.parsed["sections"]["advanced"]["fields"]["memory_slots"]
        self.assertEqual(slots["type"], "array")
        self.assertEqual(len(slots["items"]), 2)
        self.assertEqual(slots["items"][0]["slot"], "DIMM_A1")

    def test_numeric_fields(self):
        fields = self.parsed["sections"]["monitor"]["fields"]
        self.assertEqual(fields["cpu_temperature"]["value"], 42)
        self.assertAlmostEqual(fields["cpu_core_voltage"]["value"], 1.25)

    def test_unit_preserved(self):
        temp = self.parsed["sections"]["monitor"]["fields"]["cpu_temperature"]
        self.assertEqual(temp["unit"], "°C")


class TestExtractField(unittest.TestCase):
    def test_scalar(self):
        field = {"label": "Test", "type": "string", "value": "hello", "readonly": False}
        result = _extract_field(field)
        self.assertEqual(result["value"], "hello")
        self.assertEqual(result["type"], "string")

    def test_group(self):
        field = {
            "label": "Group",
            "type": "group",
            "fields": {
                "child": {"label": "Child", "type": "integer", "value": 1, "readonly": False}
            },
        }
        result = _extract_field(field)
        self.assertEqual(result["type"], "group")
        self.assertIn("child", result["fields"])

    def test_array(self):
        field = {
            "label": "Array",
            "type": "array",
            "items": [{"a": 1}, {"a": 2}],
        }
        result = _extract_field(field)
        self.assertEqual(result["type"], "array")
        self.assertEqual(len(result["items"]), 2)


class TestCountFields(unittest.TestCase):
    def test_flat_fields(self):
        fields = {
            "f1": {"type": "string", "value": "a"},
            "f2": {"type": "integer", "value": 1},
        }
        self.assertEqual(_count_fields(fields), 2)

    def test_group_field(self):
        fields = {
            "grp": {
                "type": "group",
                "fields": {
                    "c1": {"type": "string", "value": "x"},
                    "c2": {"type": "integer", "value": 0},
                },
            }
        }
        self.assertEqual(_count_fields(fields), 2)

    def test_array_field(self):
        fields = {
            "arr": {
                "type": "array",
                "items": [{"a": 1}, {"a": 2}, {"a": 3}],
            }
        }
        self.assertEqual(_count_fields(fields), 3)


class TestParseField(unittest.TestCase):
    def test_scalar_output(self):
        field = {
            "label": "BIOS Version",
            "type": "string",
            "value": "0602",
            "readonly": True,
        }
        lines = _parse_field("bios_version", field)
        self.assertEqual(len(lines), 1)
        self.assertIn("BIOS Version", lines[0])
        self.assertIn("0602", lines[0])
        self.assertIn("[읽기전용]", lines[0])

    def test_enum_shows_options(self):
        field = {
            "label": "Language",
            "type": "enum",
            "value": "English",
            "options": ["English", "Korean"],
            "readonly": False,
        }
        lines = _parse_field("lang", field)
        self.assertIn("English", lines[0])
        self.assertIn("Korean", lines[0])

    def test_group_output(self):
        field = {
            "label": "CPU Config",
            "type": "group",
            "fields": {
                "ht": {"label": "HT", "type": "enum", "value": "Enabled", "readonly": False}
            },
        }
        lines = _parse_field("cpu_config", field)
        self.assertTrue(any("CPU Config" in l for l in lines))
        self.assertTrue(any("HT" in l for l in lines))

    def test_array_output(self):
        field = {
            "label": "SATA Ports",
            "type": "array",
            "items": [{"port": "SATA1", "device": "SSD"}],
        }
        lines = _parse_field("sata_ports", field)
        self.assertTrue(any("SATA Ports" in l for l in lines))
        self.assertTrue(any("SATA1" in l for l in lines))


class TestRealJsonFile(unittest.TestCase):
    """bios_settings.json 실제 파일을 사용하는 통합 테스트."""

    def setUp(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.json_path = os.path.join(script_dir, "bios_settings.json")

    def test_file_exists(self):
        self.assertTrue(os.path.exists(self.json_path), "bios_settings.json 파일이 없습니다.")

    def test_load_and_parse(self):
        data = load_json(self.json_path)
        parsed = parse_bios_json(data)
        self.assertIn("meta", parsed)
        self.assertIn("sections", parsed)
        self.assertGreater(len(parsed["sections"]), 0)

    def test_all_sections_have_fields(self):
        data = load_json(self.json_path)
        parsed = parse_bios_json(data)
        for sec_key, sec in parsed["sections"].items():
            self.assertIn("fields", sec, f"{sec_key} 섹션에 fields가 없습니다.")
            self.assertGreater(
                len(sec["fields"]), 0, f"{sec_key} 섹션의 fields가 비어있습니다."
            )

    def test_total_field_count(self):
        data = load_json(self.json_path)
        parsed = parse_bios_json(data)
        total = sum(_count_fields(sec["fields"]) for sec in parsed["sections"].values())
        self.assertGreater(total, 0)


if __name__ == "__main__":
    unittest.main()
