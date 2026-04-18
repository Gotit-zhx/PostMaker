"""
参数验证工具
"""

import json
import ast
from datetime import datetime
from typing import List, Optional, Union

from .errors import InvalidParameterError
from .date_parser import DateParser


def _parse_string_to_list(value: str) -> List[str]:
    value = value.strip()

    if not value:
        return []

    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except json.JSONDecodeError:
        pass

    try:
        parsed = ast.literal_eval(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
        if isinstance(parsed, str):
            return [parsed]
    except (ValueError, SyntaxError):
        pass

    if ',' in value:
        items = [item.strip() for item in value.split(',')]
        return [item for item in items if item]

    return [value]


def _parse_string_to_int(value: str, param_name: str = "参数") -> int:
    value = value.strip()

    try:
        return int(value)
    except ValueError:
        pass

    try:
        return int(float(value))
    except ValueError:
        raise InvalidParameterError(
            f"{param_name} 必须是整数，无法解析: {value}",
            suggestion=f"请提供有效的整数值，如: 10, 50, 100"
        )


def validate_limit(limit: Optional[Union[int, str]], default: int = 20, max_limit: int = 1000) -> int:
    if limit is None:
        return default

    if isinstance(limit, str):
        limit = _parse_string_to_int(limit, "limit")

    if not isinstance(limit, int):
        raise InvalidParameterError("limit 参数必须是整数类型")

    if limit <= 0:
        raise InvalidParameterError("limit 必须大于0")

    if limit > max_limit:
        raise InvalidParameterError(
            f"limit 不能超过 {max_limit}",
            suggestion=f"请使用分页或降低limit值"
        )

    return limit


def validate_date(date_str: str) -> datetime:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise InvalidParameterError(
            f"日期格式错误: {date_str}",
            suggestion="请使用 YYYY-MM-DD 格式，例如: 2025-10-11"
        )


def normalize_date_range(date_range: Optional[Union[dict, str]]) -> Optional[Union[dict, str]]:
    if date_range is None:
        return None

    if isinstance(date_range, dict):
        return date_range

    if isinstance(date_range, str):
        stripped = date_range.strip()
        if stripped.startswith('{') and stripped.endswith('}'):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

    return date_range


def validate_date_range(date_range: Optional[Union[dict, str]]) -> Optional[tuple]:
    if date_range is None:
        return None

    if isinstance(date_range, str):
        stripped = date_range.strip()

        if stripped.startswith('{') and stripped.endswith('}'):
            try:
                date_range = json.loads(stripped)
            except json.JSONDecodeError as e:
                raise InvalidParameterError(
                    f"date_range JSON 解析失败: {e}",
                    suggestion='请使用正确的JSON格式: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}'
                )
        elif len(stripped) == 10 and stripped[4] == '-' and stripped[7] == '-':
            try:
                single_date = datetime.strptime(stripped, "%Y-%m-%d")
                return (single_date, single_date)
            except ValueError:
                raise InvalidParameterError(
                    f"日期格式错误: {stripped}",
                    suggestion="请使用 YYYY-MM-DD 格式，例如: 2025-10-11"
                )
        else:
            try:
                result = DateParser.resolve_date_range_expression(stripped)
                if result.get("success"):
                    dr = result["date_range"]
                    start_date = datetime.strptime(dr["start"], "%Y-%m-%d")
                    end_date = datetime.strptime(dr["end"], "%Y-%m-%d")
                    return (start_date, end_date)
                else:
                    raise InvalidParameterError(
                        f"无法识别的日期表达式: {stripped}",
                        suggestion="支持格式: YYYY-MM-DD, {\"start\": \"...\", \"end\": \"...\"}, 或自然语言"
                    )
            except InvalidParameterError:
                raise
            except Exception:
                raise InvalidParameterError(
                    f"日期解析失败: {stripped}",
                    suggestion="支持格式: YYYY-MM-DD, {\"start\": \"...\", \"end\": \"...\"}, 或自然语言"
                )

    if not isinstance(date_range, dict):
        raise InvalidParameterError(
            "date_range 必须是字典类型、日期字符串或有效的JSON字符串",
            suggestion='例如: {"start": "2025-10-01", "end": "2025-10-11"} 或 "2025-10-01"'
        )

    start_str = date_range.get("start")
    end_str = date_range.get("end")

    if not start_str or not end_str:
        raise InvalidParameterError(
            "date_range 必须包含 start 和 end 字段",
            suggestion='例如: {"start": "2025-10-01", "end": "2025-10-11"}'
        )

    start_date = validate_date(start_str)
    end_date = validate_date(end_str)

    if start_date > end_date:
        raise InvalidParameterError(
            "开始日期不能晚于结束日期",
            suggestion=f"start: {start_str}, end: {end_str}"
        )

    return (start_date, end_date)


def validate_keyword(keyword: str) -> str:
    if not keyword:
        raise InvalidParameterError("keyword 不能为空")

    if not isinstance(keyword, str):
        raise InvalidParameterError("keyword 必须是字符串类型")

    keyword = keyword.strip()

    if not keyword:
        raise InvalidParameterError("keyword 不能为空白字符")

    if len(keyword) > 100:
        raise InvalidParameterError(
            "keyword 长度不能超过100个字符",
            suggestion="请使用更简洁的关键词"
        )

    return keyword


def validate_config_section(section: Optional[str]) -> str:
    valid_sections = ["all", "crawler", "push", "keywords", "weights"]
    if section is None:
        return "all"

    if not isinstance(section, str):
        raise InvalidParameterError("section 必须是字符串类型")

    if section not in valid_sections:
        raise InvalidParameterError(
            f"无效的配置节: {section}",
            suggestion=f"支持的配置节: {', '.join(valid_sections)}"
        )

    return section


def validate_date_query(
    date_query: str,
    allow_future: bool = False,
    max_days_ago: int = 365
) -> datetime:
    if not date_query:
        raise InvalidParameterError(
            "日期查询字符串不能为空",
            suggestion="请提供日期查询，如：今天、昨天、2025-10-10"
        )

    parsed_date = DateParser.parse_date_query(date_query)

    if not allow_future:
        DateParser.validate_date_not_future(parsed_date)

    DateParser.validate_date_not_too_old(parsed_date, max_days=max_days_ago)

    return parsed_date
