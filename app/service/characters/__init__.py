# app/service/characters/__init__.py
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Tuple

DB_PATH = "app/data/characters.json"

from app.service.characters.solar_client import SolarClient

# -------------------------
# 파일 IO
# -------------------------
def _read_json_safe(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_json(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# -------------------------
# 텍스트 유틸
# -------------------------
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _clean_value(v: str) -> str:
    v = _norm(v)
    return v if v else "none"


def _strip_bullet(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^[\-\*\•]\s*", "", line)
    line = re.sub(r"^\d+[\.\)]\s*", "", line)
    return line.strip()


def _split_bullets(block: str) -> List[str]:
    if not block:
        return []
    lines = [x.strip() for x in block.splitlines() if x.strip()]
    out: List[str] = []
    for ln in lines:
        ln = _strip_bullet(ln)
        if ln:
            out.append(ln)
    return out


def _remove_footnotes(text: str) -> str:
    return re.sub(r"\[\d+\]", "", text)


def _clean_name(name: str) -> str:
    name = _remove_footnotes(name)
    name = re.sub(r"[\(\)【】\[\]]", "", name).strip()
    name = re.sub(r"\s+", " ", name).strip()
    return name


# -------------------------
# 양식형 섹션 파싱
# -------------------------
SECTION_ALIASES = {
    "age_gender": ["나이(생년월일, 없으면 나이만) /성별", "나이/성별", "나이", "생년월일", "성별"],
    "job_status": ["직업/신분", "직업", "신분"],
    "core_traits": ["핵심 특징", "핵심특징", "특징"],
    "personality": ["성격"],
    "outer_goal": ["외적 목표"],
    "inner_goal": ["내적 목표"],
    "trauma_weakness": ["트라우마/약점", "트라우마", "약점"],
    "speech_habit": ["말버릇이나 습관", "말버릇", "습관"],
    "relationships": ["다른 주요 인물과의 관계", "주요 인물과의 관계", "관계"],
}


def _detect_section(line: str) -> Tuple[str | None, str]:
    s = line.strip()
    s_no_paren = re.sub(r"\(.*?\)", "", s).strip()

    for key, aliases in SECTION_ALIASES.items():
        for a in aliases:
            if s_no_paren.startswith(a):
                if ":" in s:
                    return key, s.split(":", 1)[1].strip()
                rest = s_no_paren[len(a):].strip()
                rest = rest.lstrip("-").strip()
                return key, rest
    return None, ""


def _collect_sections(text: str) -> Dict[str, str]:
    lines = [ln.rstrip() for ln in (text or "").splitlines()]
    lines = [ln for ln in lines if ln.strip()]

    buckets: Dict[str, List[str]] = {k: [] for k in SECTION_ALIASES.keys()}
    current: str | None = None

    for ln in lines:
        key, inline = _detect_section(ln)
        if key:
            current = key
            if inline:
                buckets[current].append(inline)
            continue
        if current:
            buckets[current].append(ln.strip())

    return {k: "\n".join(v).strip() for k, v in buckets.items()}


def _parse_personality(block: str) -> Dict[str, Any]:
    if not block:
        return {"pros": "none", "cons": "none"}

    lines = [x.strip() for x in block.splitlines() if x.strip()]
    mode = None
    pros: List[str] = []
    cons: List[str] = []
    misc: List[str] = []

    for ln in lines:
        s = _strip_bullet(ln)
        if not s:
            continue

        if s.startswith("장점"):
            mode = "pros"
            after = s.split(":", 1)[1].strip() if ":" in s else s.replace("장점", "", 1).strip()
            if after:
                pros.extend(_split_bullets(after))
            continue

        if s.startswith("단점"):
            mode = "cons"
            after = s.split(":", 1)[1].strip() if ":" in s else s.replace("단점", "", 1).strip()
            if after:
                cons.extend(_split_bullets(after))
            continue

        if mode == "pros":
            pros.append(s)
        elif mode == "cons":
            cons.append(s)
        else:
            misc.append(s)

    if (not pros and not cons) and misc:
        items = _split_bullets("\n".join(misc))
        pros = items[:3]
        cons = items[3:6]

    return {
        "pros": pros[:3] if pros else "none",
        "cons": cons[:3] if cons else "none",
    }


# -------------------------
# 서술형 추출
# -------------------------
def _extract_job_status(text: str) -> str:
    candidates: List[str] = []
    keywords = [
        "외상외과의", "외과의", "일반외과", "의사", "전임 조교수", "조교수", "교수", "군의관",
        "의대", "UCL", "면허", "런던대 교수",
    ]
    for kw in keywords:
        if kw in text:
            candidates.append(kw)

    uniq: List[str] = []
    for x in candidates:
        if x not in uniq:
            uniq.append(x)

    if not uniq:
        return "none"
    return ", ".join(uniq[:5])


def _extract_trauma_weakness(text: str) -> str:
    if "뇌종양" in text and "판정" in text:
        return "뇌종양 판정 경험"
    if "결핵" in text:
        return "전쟁 중 결핵으로 죽을 뻔함"
    if "죽을 뻔" in text:
        return "생명 위협 경험"
    return "none"


def _extract_speech_habit(text: str) -> str:
    if "조선 의학" in text and ("거짓말" in text or "구라" in text):
        return "현대지식 출처를 '조선 의학'이라고 둘러대는 습관"
    return "none"


def _extract_core_traits(text: str) -> List[str] | str:
    traits: List[str] = []

    if "21세기" in text and "19세기" in text and ("다시 태어난다" in text or "환생" in text):
        traits.append("21세기 한국 출신으로 19세기 영국에서 조선인으로 다시 태어남")

    if "외상외과" in text or "일반외과" in text or "외과의" in text:
        traits.append("현대 외과(일반/외상) 전문 지식과 수술 실력 보유")

    if "조선 의학" in text and ("거짓말" in text or "구라" in text):
        traits.append("현대 지식 사용 시 '조선 의학에서 배웠다'고 위장")

    if "군의관" in text or "참전" in text or "전쟁" in text:
        traits.append("전쟁에 군의관으로 참여하며 치료/임상 경험 축적")

    uniq: List[str] = []
    for t in traits:
        if t not in uniq:
            uniq.append(t)

    return uniq if uniq else "none"


def _extract_relationships(text: str) -> List[str] | str:
    rels: List[str] = []

    if "리스턴" in text:
        if "추천" in text:
            rels.append("로버트 리스턴: 강력 추천/동료(혹은 스승급 인맥)")
        else:
            rels.append("리스턴: 동료/협업 인물(본문 기반)")
    if "나이팅게일" in text:
        rels.append("나이팅게일: 크림 전쟁 야전병원 체계 구축 협업")
    if "후원" in text or "지역 유지" in text:
        rels.append("지역 유지: 인종차별 시대에 후원자")

    uniq: List[str] = []
    for r in rels:
        if r not in uniq:
            uniq.append(r)

    return uniq if uniq else "none"


def _extract_goals(text: str) -> Tuple[str, str]:
    outer = "none"
    inner = "none"
    if "망연자실" in text or "뇌종양" in text:
        inner = "죽음/질병 경험 이후 생존과 성장에 집착하게 됨(서술 기반)"
    return outer, inner


def _extract_age_gender(text: str) -> str:
    # 나이: 21세기 같은 건 제외
    age = ""
    gender = ""

    m_age = re.search(r"(\d{1,3})\s*세(?!기)", text)
    if m_age:
        age = f"{m_age.group(1)}세"

    # 성별은 남/여 한 글자 오탐 많아서 제외
    m_gender = re.search(r"(남자|여자|남성|여성)", text)
    if m_gender:
        g = m_gender.group(1)
        gender = "남자" if g in ("남자", "남성") else "여자"

    if not age and not gender:
        return "none"
    if age and gender:
        return f"{age} / {gender}"
    return age or gender

def _extract_from_text(text: str) -> Dict[str, Any]:
    print("\n" + "="*50)
    print("🚀 [1단계] _extract_from_text 시작")
    print(f"   👉 입력된 텍스트(앞 50자): {text[:50]}...")

    if not text or not text.strip():
        print("   ⚠️ 텍스트가 비어있어서 빈 딕셔너리 리턴")
        return {}

    if SolarClient is None:
        print("   ❌ SolarClient 클래스가 없습니다 (Import 실패).")
        return {}

    try:
        print("   🔌 SolarClient 인스턴스 생성 및 호출 시도...")
        client = SolarClient()

        # 실제 AI 호출
        result = client.parse_character(text)

        print(f"   ✅ [Solar 응답 성공] 타입: {type(result)}")
        print(f"   👉 응답 내용(Keys): {list(result.keys()) if isinstance(result, dict) else 'Dict가 아님'}")
        # 내용이 너무 길 수 있으니 일부만 출력
        print(f"   👉 응답 데이터(일부): {str(result)[:100]}...")

        return result

    except Exception as e:
        print(f"   🔥 [Solar 호출 에러] {e}")
        import traceback
        traceback.print_exc() # 에러의 상세 내용을 다 보여줍니다
        return {}
    finally:
        print("🚀 [1단계] 종료")
        print("="*50 + "\n")

'''
def _extract_from_text(desc: str) -> Dict[str, Any]:
    desc = _remove_footnotes(desc or "")
    desc = _norm(desc)

    sections = _collect_sections(desc)

    age_gender = _clean_value(sections.get("age_gender", ""))
    job_status = _clean_value(sections.get("job_status", ""))

    core_traits_items = _split_bullets(sections.get("core_traits", ""))
    core_traits: Any = core_traits_items if core_traits_items else "none"

    personality = _parse_personality(sections.get("personality", ""))

    outer_goal = _clean_value(sections.get("outer_goal", ""))
    inner_goal = _clean_value(sections.get("inner_goal", ""))

    trauma_weakness = _clean_value(sections.get("trauma_weakness", ""))
    speech_habit = _clean_value(sections.get("speech_habit", ""))

    rel_items = _split_bullets(sections.get("relationships", ""))
    relationships: Any = rel_items if rel_items else "none"

    result = {
        "age_gender": age_gender,
        "job_status": job_status,
        "core_traits": core_traits,
        "personality": personality,
        "outer_goal": outer_goal,
        "inner_goal": inner_goal,
        "trauma_weakness": trauma_weakness,
        "speech_habit": speech_habit,
        "relationships": relationships,
    }

    # 양식이 거의 없으면 서술형으로 채움
    empty_cnt = 0
    for k in ["age_gender", "job_status", "core_traits", "outer_goal", "inner_goal", "trauma_weakness", "speech_habit", "relationships"]:
        if result.get(k) in ("none", "", None):
            empty_cnt += 1

    if empty_cnt >= 6:
        result.update(
            {
                "age_gender": _extract_age_gender(desc),
                "job_status": _extract_job_status(desc),
                "core_traits": _extract_core_traits(desc),
                "outer_goal": _extract_goals(desc)[0],
                "inner_goal": _extract_goals(desc)[1],
                "trauma_weakness": _extract_trauma_weakness(desc),
                "speech_habit": _extract_speech_habit(desc),
                "relationships": _extract_relationships(desc),
                "personality": result.get("personality") or {"pros": "none", "cons": "none"},
            }
        )

    return result
'''

# -------------------------
# MERGE(보완/수정) 로직
# -------------------------
def _uniq_keep_order(items: List[str]) -> List[str]:
    out: List[str] = []
    for x in items:
        x = _norm(x)
        if not x or x == "none":
            continue
        if x not in out:
            out.append(x)
    return out


def _merge_comma_tags(old: str, new: str) -> str:
    old = _clean_value(old)
    new = _clean_value(new)
    if old == "none" and new == "none":
        return "none"
    if old == "none":
        return new
    if new == "none":
        return old

    old_parts = [p.strip() for p in old.split(",") if p.strip()]
    new_parts = [p.strip() for p in new.split(",") if p.strip()]
    merged = _uniq_keep_order(new_parts + old_parts)  # 새 내용을 우선
    return ", ".join(merged)


def _parse_age_gender_parts(s: str) -> Tuple[str, str]:
    s = _clean_value(s)
    if s == "none":
        return "", ""

    age = ""
    gender = ""
    m_age = re.search(r"(\d{1,3})\s*세(?!기)", s)
    if m_age:
        age = f"{m_age.group(1)}세"

    m_gender = re.search(r"(남자|여자|남성|여성)", s)
    if m_gender:
        g = m_gender.group(1)
        gender = "남자" if g in ("남자", "남성") else "여자"

    return age, gender


def _merge_age_gender(old: str, new: str) -> str:
    old_age, old_gender = _parse_age_gender_parts(old)
    new_age, new_gender = _parse_age_gender_parts(new)

    age = new_age or old_age
    gender = new_gender or old_gender

    if not age and not gender:
        return "none"
    if age and gender:
        return f"{age} / {gender}"
    return age or gender


def _merge_list_field(old_val: Any, new_val: Any, *, max_items: int = 10) -> Any:
    # old/new가 "none" or list 둘 다 처리
    old_list: List[str] = []
    new_list: List[str] = []

    if isinstance(old_val, list):
        old_list = old_val
    elif isinstance(old_val, str) and old_val != "none":
        old_list = [old_val]

    if isinstance(new_val, list):
        new_list = new_val
    elif isinstance(new_val, str) and new_val != "none":
        new_list = [new_val]

    merged = _uniq_keep_order(new_list + old_list)  # 새 정보 우선
    if not merged:
        return "none"
    return merged[:max_items]


def _merge_personality(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    old = old if isinstance(old, dict) else {"pros": "none", "cons": "none"}
    new = new if isinstance(new, dict) else {"pros": "none", "cons": "none"}

    def to_list(x: Any) -> List[str]:
        if isinstance(x, list):
            return x
        if isinstance(x, str) and x != "none":
            return [x]
        return []

    pros = _uniq_keep_order(to_list(new.get("pros")) + to_list(old.get("pros")))
    cons = _uniq_keep_order(to_list(new.get("cons")) + to_list(old.get("cons")))

    return {
        "pros": pros[:3] if pros else "none",
        "cons": cons[:3] if cons else "none",
    }


def _merge_character(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """
    규칙:
    - new가 'none'이면 old 유지
    - 문자열 필드: new가 의미 있으면 교체 (단 age_gender는 부분 병합)
    - 리스트 필드(core_traits/relationships): 합치고 중복 제거 (새 내용 우선)
    - job_status: 콤마 태그 병합
    - personality: pros/cons 병합
    """
    merged = dict(old)

    merged["name"] = old.get("name") or new.get("name")

    merged["age_gender"] = _merge_age_gender(old.get("age_gender", "none"), new.get("age_gender", "none"))
    merged["job_status"] = _merge_comma_tags(old.get("job_status", "none"), new.get("job_status", "none"))

    merged["core_traits"] = _merge_list_field(old.get("core_traits", "none"), new.get("core_traits", "none"), max_items=10)
    merged["relationships"] = _merge_list_field(old.get("relationships", "none"), new.get("relationships", "none"), max_items=20)

    merged["personality"] = _merge_personality(old.get("personality", {}), new.get("personality", {}))

    for k in ["outer_goal", "inner_goal", "trauma_weakness", "speech_habit"]:
        nv = _clean_value(new.get(k, "none"))
        if nv != "none":
            merged[k] = nv
        else:
            merged[k] = _clean_value(old.get(k, "none"))

    # 빈 값 정리
    for k in ["age_gender", "job_status", "outer_goal", "inner_goal", "trauma_weakness", "speech_habit"]:
        merged[k] = _clean_value(merged.get(k, "none"))

    if merged.get("core_traits") == []:
        merged["core_traits"] = "none"
    if merged.get("relationships") == []:
        merged["relationships"] = "none"

    return merged


# -------------------------
# 공개 함수
# -------------------------
def parse_character_with_name(name: str, features: str) -> Dict[str, Any]:
    print(f"🧩 [2단계] parse_character_with_name 호출됨 (이름: {name})")

    nm = _clean_name(name)
    if not nm:
        raise ValueError("name is required")

    extracted = _extract_from_text(features or "")

    print(f"   🔄 [병합 중] 최종 JSON 조립 시작...")

    # ✅ 안전하게 데이터를 가져오기 위한 헬퍼 로직 적용
    final_data = {
        "name": nm,
        "age_gender": extracted.get("age_gender") or "none",
        "job_status": extracted.get("job_status") or "none",
        # core_traits가 리스트가 아니면 빈 리스트로 강제 변환
        "core_traits": extracted.get("core_traits") if isinstance(extracted.get("core_traits"), list) else [],
        "personality": extracted.get("personality") if isinstance(extracted.get("personality"), dict) else {"pros": "none", "cons": "none"},
        "outer_goal": extracted.get("outer_goal") or "none",
        "inner_goal": extracted.get("inner_goal") or "none",
        "trauma_weakness": extracted.get("trauma_weakness") or "none",
        "speech_habit": extracted.get("speech_habit") or "none",
        # relationships가 리스트가 아니면 빈 리스트로 강제 변환
        "relationships": extracted.get("relationships") if isinstance(extracted.get("relationships"), list) else [],
        # ✅ additional_settings 누락 방지 (빈 딕셔너리라도 넣어줌)
        "additional_settings": extracted.get("additional_settings") if isinstance(extracted.get("additional_settings"), dict) else {}
    }

    return final_data

def _clean_name(name: str) -> str:
    if not name: return ""
    return name.strip()


def upsert_character(name: str, features: str, *, db_path: str = DB_PATH) -> Dict[str, Any]:
    """
    ✅ 같은 이름이면 overwrite가 아니라 merge(보완/수정)
    """
    new_obj = parse_character_with_name(name, features)
    key = new_obj["name"]

    db = _read_json_safe(db_path)
    existed = key in db

    if existed and isinstance(db.get(key), dict):
        merged = _merge_character(db[key], new_obj)
        db[key] = merged
        saved = merged
        action = "merged"
    else:
        db[key] = new_obj
        saved = new_obj
        action = "inserted"

    _write_json(db_path, db)

    return {
        "status": "success",
        "action": action,
        "name": key,
        "saved": saved,
        "count": len(db),
        "db_path": db_path,
    }


__all__ = ["upsert_character", "parse_character_with_name", "DB_PATH"]