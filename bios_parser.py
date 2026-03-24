"""
bios_parser.py
BIOS 설정 JSON 파일을 완벽하게 파싱하는 모듈.
Parse BIOS settings JSON files completely.
"""

import json
import os
from typing import Any


def load_json(filepath: str) -> dict:
    """JSON 파일을 읽어 딕셔너리로 반환한다."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {filepath}")
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


def _parse_field(key: str, field: dict, indent: int = 0) -> list[str]:
    """
    단일 필드(또는 중첩 그룹/배열)를 재귀적으로 파싱해
    출력 라인 목록으로 반환한다.
    """
    lines: list[str] = []
    prefix = "  " * indent
    field_type = field.get("type", "unknown")
    label = field.get("label", key)

    if field_type == "group":
        lines.append(f"{prefix}[{label}]")
        for sub_key, sub_field in field.get("fields", {}).items():
            lines.extend(_parse_field(sub_key, sub_field, indent + 1))

    elif field_type == "array":
        lines.append(f"{prefix}[{label}]")
        for idx, item in enumerate(field.get("items", []), start=1):
            lines.append(f"{prefix}  항목 {idx}:")
            for item_key, item_val in item.items():
                lines.append(f"{prefix}    {item_key}: {item_val}")

    else:
        value = field.get("value")
        unit = field.get("unit", "")
        value_str = f"{value} {unit}".strip() if value is not None else "N/A"
        readonly_tag = " [읽기전용]" if field.get("readonly", False) else ""
        options_str = ""
        if "options" in field:
            options_str = f"  (선택지: {', '.join(str(o) for o in field['options'])})"
        lines.append(
            f"{prefix}{label}: {value_str}{readonly_tag}{options_str}"
        )

    return lines


def _parse_section(section_key: str, section: dict, indent: int = 0) -> list[str]:
    """섹션 하나를 파싱해 출력 라인 목록으로 반환한다."""
    lines: list[str] = []
    prefix = "  " * indent
    label = section.get("label", section_key)
    lines.append(f"{prefix}{'=' * 60}")
    lines.append(f"{prefix}섹션: {label}")
    lines.append(f"{prefix}{'=' * 60}")

    for field_key, field in section.get("fields", {}).items():
        lines.extend(_parse_field(field_key, field, indent + 1))

    return lines


def parse_bios_json(data: dict) -> dict[str, Any]:
    """
    BIOS JSON 데이터 전체를 파싱해 구조화된 결과를 반환한다.

    반환값:
        {
            "meta": { version, manufacturer, product, date },
            "sections": { section_key: { label, fields: { ... } } }
        }
    """
    bios = data.get("bios", {})
    result: dict[str, Any] = {
        "meta": {
            "version": bios.get("version"),
            "manufacturer": bios.get("manufacturer"),
            "product": bios.get("product"),
            "date": bios.get("date"),
        },
        "sections": {},
    }

    for section_key, section in bios.get("sections", {}).items():
        parsed_section: dict[str, Any] = {
            "label": section.get("label", section_key),
            "fields": {},
        }
        for field_key, field in section.get("fields", {}).items():
            parsed_section["fields"][field_key] = _extract_field(field)
        result["sections"][section_key] = parsed_section

    return result


def _extract_field(field: dict) -> Any:
    """필드 하나를 재귀적으로 추출해 파이썬 자료형으로 반환한다."""
    field_type = field.get("type", "unknown")

    if field_type == "group":
        return {
            "type": "group",
            "label": field.get("label"),
            "fields": {k: _extract_field(v) for k, v in field.get("fields", {}).items()},
        }

    if field_type == "array":
        return {
            "type": "array",
            "label": field.get("label"),
            "items": field.get("items", []),
        }

    return {
        "type": field_type,
        "label": field.get("label"),
        "value": field.get("value"),
        "unit": field.get("unit"),
        "readonly": field.get("readonly", False),
        "options": field.get("options"),
        "min": field.get("min"),
        "max": field.get("max"),
    }


def print_bios(data: dict) -> None:
    """파싱된 BIOS JSON 데이터를 사람이 읽기 쉬운 형식으로 출력한다."""
    bios = data.get("bios", {})
    print("=" * 60)
    print("BIOS 설정 파싱 결과")
    print("=" * 60)
    print(f"제조사  : {bios.get('manufacturer', 'N/A')}")
    print(f"제품명  : {bios.get('product', 'N/A')}")
    print(f"버전    : {bios.get('version', 'N/A')}")
    print(f"날짜    : {bios.get('date', 'N/A')}")
    print()

    for section_key, section in bios.get("sections", {}).items():
        for line in _parse_section(section_key, section):
            print(line)
        print()


def main() -> None:
    """CLI 진입점: bios_settings.json 을 파싱해 출력한다."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, "bios_settings.json")

    print(f"파일 로드 중: {json_path}\n")
    data = load_json(json_path)
    print_bios(data)
    parsed = parse_bios_json(data)
    print()
    print("=== 파싱 완료 ===")
    print(f"총 섹션 수: {len(parsed['sections'])}")
    for sec_key, sec in parsed["sections"].items():
        field_count = _count_fields(sec["fields"])
        print(f"  - {sec['label']}: {field_count}개 항목")


def _count_fields(fields: dict) -> int:
    """중첩 필드를 포함해 전체 단말 필드 수를 반환한다."""
    count = 0
    for field in fields.values():
        if isinstance(field, dict):
            if field.get("type") == "group":
                count += _count_fields(field.get("fields", {}))
            elif field.get("type") == "array":
                count += len(field.get("items", []))
            else:
                count += 1
        else:
            count += 1
    return count


if __name__ == "__main__":
    main()
