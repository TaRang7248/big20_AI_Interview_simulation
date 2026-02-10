"""
PDF 리포트 생성 서비스 (PDF Report Service)
============================================
REQ-F-006 구현: 면접 리포트 PDF 내보내기

기능:
  - 면접 종합 리포트를 PDF 형식으로 생성
  - STAR 분석, LLM 평가, 발화 속도, 시선 추적, 감정 분석 결과 포함
  - 한국어 지원 (시스템 폰트 자동 탐색)
  - 차트/바 그래프 시각화 포함

의존성:
  pip install reportlab
"""

from __future__ import annotations

import io
import os
import platform
from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    HRFlowable,
    Image,
)
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics import renderPDF


# ========== 한글 폰트 설정 ==========

_FONT_REGISTERED = False
FONT_NAME = "Helvetica"  # fallback

def _find_korean_font() -> Optional[str]:
    """시스템에서 사용 가능한 한글 폰트를 찾습니다."""
    candidates = []
    
    if platform.system() == "Windows":
        font_dir = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
        candidates = [
            os.path.join(font_dir, "malgun.ttf"),       # 맑은 고딕
            os.path.join(font_dir, "NanumGothic.ttf"),   # 나눔고딕
            os.path.join(font_dir, "gulim.ttc"),         # 굴림
            os.path.join(font_dir, "batang.ttc"),        # 바탕
        ]
    elif platform.system() == "Linux":
        candidates = [
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    elif platform.system() == "Darwin":
        candidates = [
            "/Library/Fonts/AppleGothic.ttf",
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        ]
    
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _ensure_font():
    """한글 폰트를 등록합니다."""
    global _FONT_REGISTERED, FONT_NAME
    if _FONT_REGISTERED:
        return
    
    font_path = _find_korean_font()
    if font_path:
        try:
            pdfmetrics.registerFont(TTFont("KoreanFont", font_path))
            FONT_NAME = "KoreanFont"
            _FONT_REGISTERED = True
            return
        except Exception:
            pass
    
    # 폰트를 못 찾으면 Helvetica 사용 (한글 깨짐)
    _FONT_REGISTERED = True


# ========== 스타일 정의 ==========

def _get_styles() -> Dict[str, ParagraphStyle]:
    _ensure_font()
    
    base = getSampleStyleSheet()
    
    styles = {
        "title": ParagraphStyle(
            "Title_Custom",
            parent=base["Title"],
            fontName=FONT_NAME,
            fontSize=22,
            textColor=colors.HexColor("#1a237e"),
            spaceAfter=8 * mm,
            alignment=1,  # center
        ),
        "subtitle": ParagraphStyle(
            "Subtitle_Custom",
            parent=base["Normal"],
            fontName=FONT_NAME,
            fontSize=10,
            textColor=colors.HexColor("#666666"),
            spaceAfter=6 * mm,
            alignment=1,
        ),
        "heading": ParagraphStyle(
            "Heading_Custom",
            parent=base["Heading2"],
            fontName=FONT_NAME,
            fontSize=14,
            textColor=colors.HexColor("#0d47a1"),
            spaceBefore=6 * mm,
            spaceAfter=3 * mm,
            borderWidth=0,
            borderColor=colors.HexColor("#1565c0"),
            borderPadding=2,
        ),
        "subheading": ParagraphStyle(
            "SubHeading_Custom",
            parent=base["Heading3"],
            fontName=FONT_NAME,
            fontSize=11,
            textColor=colors.HexColor("#1565c0"),
            spaceBefore=3 * mm,
            spaceAfter=2 * mm,
        ),
        "body": ParagraphStyle(
            "Body_Custom",
            parent=base["Normal"],
            fontName=FONT_NAME,
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#333333"),
            spaceAfter=2 * mm,
        ),
        "bullet": ParagraphStyle(
            "Bullet_Custom",
            parent=base["Normal"],
            fontName=FONT_NAME,
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#444444"),
            leftIndent=8 * mm,
            spaceAfter=1.5 * mm,
            bulletIndent=3 * mm,
        ),
        "grade_s": ParagraphStyle("GradeS", parent=base["Normal"], fontName=FONT_NAME, fontSize=12, textColor=colors.HexColor("#1b5e20")),
        "grade_a": ParagraphStyle("GradeA", parent=base["Normal"], fontName=FONT_NAME, fontSize=12, textColor=colors.HexColor("#2e7d32")),
        "grade_b": ParagraphStyle("GradeB", parent=base["Normal"], fontName=FONT_NAME, fontSize=12, textColor=colors.HexColor("#f57f17")),
        "grade_c": ParagraphStyle("GradeC", parent=base["Normal"], fontName=FONT_NAME, fontSize=12, textColor=colors.HexColor("#e65100")),
        "grade_d": ParagraphStyle("GradeD", parent=base["Normal"], fontName=FONT_NAME, fontSize=12, textColor=colors.HexColor("#b71c1c")),
    }
    return styles


# ========== 시각화 유틸 ==========

def _draw_bar(label: str, value: float, max_val: float, bar_width: float = 300) -> Drawing:
    """수평 바 차트 한 줄"""
    d = Drawing(bar_width + 100, 20)
    ratio = min(value / max_val, 1.0) if max_val > 0 else 0
    
    # 배경
    d.add(Rect(80, 4, bar_width, 12, fillColor=colors.HexColor("#e0e0e0"), strokeColor=None))
    # 값
    bar_color = colors.HexColor("#1565c0") if ratio >= 0.6 else (
        colors.HexColor("#ff9800") if ratio >= 0.3 else colors.HexColor("#e53935")
    )
    d.add(Rect(80, 4, bar_width * ratio, 12, fillColor=bar_color, strokeColor=None))
    # 라벨
    _ensure_font()
    d.add(String(0, 6, label, fontName=FONT_NAME, fontSize=9, fillColor=colors.HexColor("#333333")))
    # 값 텍스트
    d.add(String(bar_width + 85, 6, f"{value:.1f}", fontName=FONT_NAME, fontSize=9, fillColor=colors.HexColor("#333333")))
    return d


def _grade_color(grade: str) -> str:
    """등급별 색상"""
    return {
        "S": "#1b5e20", "A": "#2e7d32", "B": "#f57f17", 
        "C": "#e65100", "D": "#b71c1c"
    }.get(grade, "#333333")


# ========== 메인 PDF 생성 함수 ==========

def generate_pdf_report(report_data: Dict[str, Any]) -> bytes:
    """면접 종합 리포트를 PDF로 생성합니다.
    
    Args:
        report_data: 리포트 데이터 딕셔너리
            필수 필드:
                - session_id, generated_at, metrics, star_analysis, keywords, feedback
            선택 필드:
                - llm_evaluation: LLM 평가 결과
                - speech_analysis: 발화 분석 결과
                - gaze_analysis: 시선 분석 결과
                - emotion_stats: 감정 분석 결과
                - grade: 종합 등급
    
    Returns:
        PDF 바이트 데이터
    """
    _ensure_font()
    styles = _get_styles()
    
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )
    
    elements: List = []
    
    # ========== 표지 ==========
    elements.append(Spacer(1, 3 * cm))
    elements.append(Paragraph("AI 모의면접 종합 리포트", styles["title"]))
    elements.append(Paragraph(
        f"세션 ID: {report_data.get('session_id', 'N/A')}", styles["subtitle"]
    ))
    elements.append(Paragraph(
        f"생성일시: {report_data.get('generated_at', datetime.now().isoformat())[:19].replace('T', ' ')}",
        styles["subtitle"]
    ))
    
    # 종합 등급이 있으면 크게 표시
    grade = report_data.get("grade", "")
    if grade:
        grade_style_key = f"grade_{grade.lower()}" if f"grade_{grade.lower()}" in styles else "body"
        elements.append(Spacer(1, 1 * cm))
        elements.append(Paragraph(
            f"<font size='36' color='{_grade_color(grade)}'><b>{grade}</b></font>",
            ParagraphStyle("CenterGrade", parent=styles["body"], alignment=1, fontSize=36)
        ))
        elements.append(Paragraph("종합 등급", styles["subtitle"]))
    
    elements.append(Spacer(1, 1 * cm))
    elements.append(HRFlowable(width="100%", color=colors.HexColor("#1565c0"), thickness=2))
    
    # ========== 1. 답변 기본 통계 ==========
    elements.append(Paragraph("1. 답변 기본 통계", styles["heading"]))
    
    metrics = report_data.get("metrics", {})
    stats_data = [
        ["항목", "값"],
        ["총 답변 수", f"{metrics.get('total', 0)}회"],
        ["평균 답변 길이", f"{metrics.get('avg_length', 0)}자"],
        ["총 답변 분량", f"{metrics.get('total_chars', 0)}자"],
    ]
    stats_table = Table(stats_data, colWidths=[6 * cm, 8 * cm])
    stats_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1565c0")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(stats_table)
    
    # ========== 2. STAR 기법 분석 ==========
    elements.append(Paragraph("2. STAR 기법 분석", styles["heading"]))
    
    star = report_data.get("star_analysis", {})
    star_labels = {
        "situation": "상황 (S)", "task": "과제 (T)",
        "action": "행동 (A)", "result": "결과 (R)"
    }
    
    max_star = max((star.get(k, {}).get("count", 0) for k in star_labels), default=1) or 1
    for key, label in star_labels.items():
        count = star.get(key, {}).get("count", 0)
        elements.append(_draw_bar(label, count, max(max_star, 5)))
    
    # ========== 3. LLM 평가 결과 ==========
    llm_eval = report_data.get("llm_evaluation")
    if llm_eval:
        elements.append(Paragraph("3. AI 답변 평가 (LLM)", styles["heading"]))
        
        avg_scores = llm_eval.get("average_scores", {})
        total_avg = llm_eval.get("total_average", 0)
        
        score_labels = {
            "specificity": "구체성", "logic": "논리성",
            "technical": "기술 이해도", "star": "STAR 기법", "communication": "전달력"
        }
        
        for key, label in score_labels.items():
            val = avg_scores.get(key, 0)
            elements.append(_draw_bar(label, val, 5))
        
        elements.append(Spacer(1, 2 * mm))
        elements.append(Paragraph(
            f"<b>평균 점수: {total_avg:.1f} / 5.0점</b>  |  답변 수: {llm_eval.get('answer_count', 0)}개",
            styles["body"]
        ))
    
    # ========== 4. 발화 분석 ==========
    speech = report_data.get("speech_analysis")
    if speech:
        elements.append(Paragraph("4. 발화 속도 및 발음 분석", styles["heading"]))
        
        speech_data = [
            ["항목", "값", "등급"],
            ["평균 발화 속도", f"{speech.get('avg_speech_rate_spm', 0):.0f} SPM (분당 음절)", speech.get("speech_rate_grade", "N/A")],
            ["평균 어절 속도", f"{speech.get('avg_speech_rate_wpm', 0):.0f} WPM (분당 어절)", ""],
            ["발음 명확도", f"{speech.get('avg_confidence', 0):.1%}", speech.get("pronunciation_grade", "N/A")],
            ["총 발화 시간", f"{speech.get('total_duration_seconds', 0):.0f}초", ""],
            ["필러 횟수", f"{speech.get('total_fillers', 0)}회", ""],
            ["침묵 횟수", f"{speech.get('total_pauses', 0)}회", ""],
        ]
        speech_table = Table(speech_data, colWidths=[5 * cm, 6 * cm, 3 * cm])
        speech_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d47a1")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(speech_table)
        
        # 평가 텍스트
        elements.append(Spacer(1, 2 * mm))
        assessment = speech.get("speech_rate_assessment", "")
        if assessment:
            elements.append(Paragraph(f"<b>발화 속도:</b> {assessment}", styles["body"]))
        pron_assessment = speech.get("pronunciation_assessment", "")
        if pron_assessment:
            elements.append(Paragraph(f"<b>발음 명확성:</b> {pron_assessment}", styles["body"]))
    
    # ========== 5. 시선 분석 ==========
    gaze = report_data.get("gaze_analysis")
    if gaze:
        section_num = 5 if speech else 4
        elements.append(Paragraph(f"{section_num}. 시선 처리 (Eye Contact) 분석", styles["heading"]))
        
        gaze_data = [
            ["항목", "값", "등급"],
            ["정면 응시 비율", gaze.get("eye_contact_percentage", "N/A"), gaze.get("eye_contact_grade", "N/A")],
            ["시선 이탈 비율", f"{gaze.get('away_ratio', 0):.1%}", ""],
            ["시선 안정성", f"{gaze.get('consistency_score', 0):.1%}", ""],
            ["총 분석 샘플", f"{gaze.get('total_samples', 0)}개", ""],
        ]
        gaze_table = Table(gaze_data, colWidths=[5 * cm, 6 * cm, 3 * cm])
        gaze_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d47a1")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(gaze_table)
        
        # 시선 방향 분포 바
        dist = gaze.get("direction_distribution", {})
        if dist:
            elements.append(Spacer(1, 2 * mm))
            elements.append(Paragraph("<b>시선 방향 분포:</b>", styles["body"]))
            dir_labels = {
                "center": "정면", "left": "좌측", "right": "우측",
                "up": "상단", "down": "하단", "away": "이탈"
            }
            for dk, dl in dir_labels.items():
                val = dist.get(dk, 0) * 100
                elements.append(_draw_bar(dl, val, 100))
        
        assessment = gaze.get("eye_contact_assessment", "")
        if assessment:
            elements.append(Spacer(1, 2 * mm))
            elements.append(Paragraph(f"<b>시선 평가:</b> {assessment}", styles["body"]))
    
    # ========== 6. 감정 분석 ==========
    emotion = report_data.get("emotion_stats")
    if emotion and isinstance(emotion, dict):
        section_num = (5 if not speech else 5) + (1 if gaze else 0) + (1 if speech else 0)
        elements.append(Paragraph(f"{section_num}. 감정 분석", styles["heading"]))
        
        dominant = emotion.get("dominant_emotion", "")
        probabilities = emotion.get("probabilities", {})
        if dominant:
            emo_labels = {"happy": "행복", "neutral": "중립", "sad": "슬픔", "angry": "분노", 
                        "surprise": "놀람", "fear": "공포", "disgust": "혐오"}
            elements.append(Paragraph(f"<b>주요 감정:</b> {emo_labels.get(dominant, dominant)}", styles["body"]))
            
            if probabilities:
                for emo, prob in sorted(probabilities.items(), key=lambda x: x[1], reverse=True):
                    label = emo_labels.get(emo, emo)
                    elements.append(_draw_bar(label, prob * 100, 100))
    
    # ========== 7. 핵심 키워드 ==========
    keywords = report_data.get("keywords", {})
    if keywords:
        elements.append(Paragraph("핵심 키워드 분석", styles["heading"]))
        
        tech_kw = keywords.get("tech_keywords", [])
        if tech_kw:
            elements.append(Paragraph("<b>기술 키워드:</b>", styles["body"]))
            kw_str = ", ".join([f"{kw} ({cnt}회)" for kw, cnt in tech_kw[:8]])
            elements.append(Paragraph(f"  {kw_str}", styles["bullet"]))
        
        gen_kw = keywords.get("general_keywords", [])
        if gen_kw:
            elements.append(Paragraph("<b>주요 표현:</b>", styles["body"]))
            kw_str = ", ".join([f"{kw} ({cnt}회)" for kw, cnt in gen_kw[:10]])
            elements.append(Paragraph(f"  {kw_str}", styles["bullet"]))
    
    # ========== 8. 종합 피드백 ==========
    feedback = report_data.get("feedback", [])
    if feedback:
        elements.append(Paragraph("종합 피드백 및 개선 제안", styles["heading"]))
        for fb in feedback:
            elements.append(Paragraph(f"• {fb}", styles["bullet"]))
    
    # ========== 푸터 ==========
    elements.append(Spacer(1, 1 * cm))
    elements.append(HRFlowable(width="100%", color=colors.HexColor("#cccccc"), thickness=1))
    elements.append(Paragraph(
        "본 리포트는 AI 모의면접 시스템에 의해 자동 생성되었습니다.",
        ParagraphStyle("Footer", parent=styles["body"], fontSize=8, textColor=colors.HexColor("#999999"), alignment=1)
    ))
    
    # ========== 빌드 ==========
    doc.build(elements)
    return buf.getvalue()
