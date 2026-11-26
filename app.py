import streamlit as st
import sqlite3
import calendar
from datetime import date

st.set_page_config(page_title="MONEY:LOG", page_icon="💰", layout="wide")

# 기존 moneylog.db를 그대로 사용합니다.
conn = sqlite3.connect("moneylog.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expense_date TEXT,
    amount INTEGER,
    category TEXT,
    payment TEXT,
    memo TEXT
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS settings (
    name TEXT PRIMARY KEY,
    value INTEGER
)
""")
cur.execute("INSERT OR IGNORE INTO settings (name, value) VALUES ('budget', 1000000)")
conn.commit()

budget = cur.execute("SELECT value FROM settings WHERE name='budget'").fetchone()[0]
CATEGORIES = ["식비", "카페", "쇼핑", "교통", "여가", "건강", "교육", "생활", "기타"]
PAYMENTS = ["카드", "현금", "계좌이체", "기타"]
today = date.today()
this_month = today.strftime("%Y-%m")

# 사이드바
st.sidebar.title("💰 MONEY:LOG")
st.sidebar.caption("MY PERSONAL FINANCE")
menu = st.sidebar.radio("MENU", ["홈", "소비 기록", "소비 통계", "월간 보고서"])
st.sidebar.divider()
st.sidebar.caption("나의 소비를 기록하고 이해하는 가계부")

st.title(f"💰 MONEY:LOG  /  {menu}")
st.caption("나의 소비를 기록하고 이해하는 가계부")
st.divider()

# 공통 데이터
monthly_total = cur.execute(
    "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE expense_date LIKE ?",
    (this_month + "%",)
).fetchone()[0]
remaining = budget - monthly_total
all_rows = cur.execute("""
    SELECT id, expense_date, amount, category, payment, memo
    FROM expenses ORDER BY expense_date DESC, id DESC
""").fetchall()

# 홈
if menu == "홈":
    st.header("이번 달 한눈에 보기")
    c1, c2, c3 = st.columns(3)
    c1.metric("이번 달 총지출", f"{monthly_total:,}원")
    c2.metric("이번 달 예산", f"{budget:,}원")
    c3.metric("남은 예산", f"{remaining:,}원")

    st.progress(min(monthly_total / budget, 1.0) if budget > 0 else 0)
    if budget > 0:
        usage = monthly_total / budget * 100
        if usage >= 100:
            st.error(f"🚨 이번 달 예산을 {monthly_total - budget:,}원 초과했어요.")
        elif usage >= 80:
            st.warning(f"⚠️ 예산의 {usage:.1f}%를 사용했어요. 남은 예산을 확인해 주세요.")
        else:
            st.success(f"👍 예산의 {usage:.1f}%를 사용했어요. 좋은 흐름이에요!")

    st.divider()
    st.subheader("⚙️ 월 예산 설정")
    with st.form("budget_form"):
        new_budget = st.number_input("이번 달 예산 (원)", min_value=0, value=int(budget), step=10000)
        if st.form_submit_button("예산 저장"):
            cur.execute("UPDATE settings SET value=?", (new_budget,))
            conn.commit()
            st.success("예산이 저장되었습니다!")
            st.rerun()

    st.divider()
    st.subheader("🧾 최근 소비 내역")
    if all_rows:
        st.dataframe([
            {"날짜": r[1], "금액": f"{r[2]:,}원", "카테고리": r[3],
             "결제 수단": r[4], "메모": r[5] or "-"}
            for r in all_rows[:5]
        ], use_container_width=True, hide_index=True)
    else:
        st.info("아직 소비 기록이 없어요. '소비 기록' 메뉴에서 첫 기록을 추가해 보세요.")

# 소비 기록
elif menu == "소비 기록":
    st.header("✏️ 새로운 소비 기록")
    with st.form("expense_form", clear_on_submit=True):
        expense_date = st.date_input("날짜", value=today)
        amount = st.number_input("금액 (원)", min_value=0, step=1000)
        category = st.selectbox("카테고리", CATEGORIES)
        payment = st.selectbox("결제 수단", PAYMENTS)
        memo = st.text_input("메모", placeholder="예: 점심 식사")
        submitted = st.form_submit_button("소비 기록 저장")
        if submitted:
            if amount <= 0:
                st.warning("금액을 입력해 주세요.")
            else:
                cur.execute(
                    """INSERT INTO expenses (expense_date, amount, category, payment, memo)
                    VALUES (?, ?, ?, ?, ?)""",
                    (str(expense_date), int(amount), category, payment, memo)
                )
                conn.commit()
                st.success("소비 기록이 저장되었습니다!")
                st.rerun()

    st.divider()
    st.header("📋 소비 내역 관리")
    month_options = ["전체"] + sorted({r[1][:7] for r in all_rows}, reverse=True)
    selected_month = st.selectbox("조회할 월", month_options, key="records_month")
    rows = all_rows if selected_month == "전체" else [r for r in all_rows if r[1].startswith(selected_month)]

    if rows:
        st.dataframe([
            {"날짜": r[1], "금액": f"{r[2]:,}원", "카테고리": r[3],
             "결제 수단": r[4], "메모": r[5] or "-"}
            for r in rows
        ], use_container_width=True, hide_index=True)

        st.subheader("✏️ 소비 내역 수정")
        edit_id = st.selectbox(
            "수정할 기록 선택", [r[0] for r in rows],
            format_func=lambda x: next(
                f"{r[1]} | {r[2]:,}원 | {r[3]} | {r[5] or '-'}" for r in rows if r[0] == x
            ), key="edit_id"
        )
        edit_row = next(r for r in rows if r[0] == edit_id)
        with st.form("edit_form"):
            edit_date = st.date_input("날짜 수정", value=date.fromisoformat(edit_row[1]))
            edit_amount = st.number_input("금액 수정", min_value=1, value=int(edit_row[2]), step=1000)
            edit_category = st.selectbox("카테고리 수정", CATEGORIES, index=CATEGORIES.index(edit_row[3]))
            edit_payment = st.selectbox("결제 수단 수정", PAYMENTS, index=PAYMENTS.index(edit_row[4]))
            edit_memo = st.text_input("메모 수정", value=edit_row[5] or "")
            if st.form_submit_button("수정 내용 저장"):
                cur.execute("""
                    UPDATE expenses SET expense_date=?, amount=?, category=?, payment=?, memo=?
                    WHERE id=?
                """, (str(edit_date), int(edit_amount), edit_category, edit_payment, edit_memo, edit_id))
                conn.commit()
                st.success("소비 기록이 수정되었습니다!")
                st.rerun()

        st.subheader("🗑️ 소비 내역 삭제")
        delete_id = st.selectbox(
            "삭제할 기록 선택", [r[0] for r in rows],
            format_func=lambda x: next(
                f"{r[1]} | {r[2]:,}원 | {r[3]} | {r[5] or '-'}" for r in rows if r[0] == x
            ), key="delete_id"
        )
        if st.button("선택한 기록 삭제"):
            cur.execute("DELETE FROM expenses WHERE id=?", (delete_id,))
            conn.commit()
            st.success("기록이 삭제되었습니다.")
            st.rerun()
    else:
        st.info("선택한 기간에 소비 기록이 없습니다.")

# 소비 통계
elif menu == "소비 통계":
    st.header("📊 나의 소비 통계")
    month_options = ["전체"] + sorted({r[1][:7] for r in all_rows}, reverse=True)
    selected_month = st.selectbox("분석할 월", month_options, key="stats_month")
    rows = all_rows if selected_month == "전체" else [r for r in all_rows if r[1].startswith(selected_month)]

    if rows:
        category_totals = {}
        daily_totals = {}
        for r in rows:
            category_totals[r[3]] = category_totals.get(r[3], 0) + r[2]
            daily_totals[r[1]] = daily_totals.get(r[1], 0) + r[2]

        total_spending = sum(category_totals.values())
        top_category = max(category_totals, key=category_totals.get)
        average_daily = total_spending / len(daily_totals)
        highest_day = max(daily_totals, key=daily_totals.get)

        c1, c2, c3 = st.columns(3)
        c1.metric("조회 기간 총지출", f"{total_spending:,}원")
        c2.metric("최다 지출 카테고리", top_category)
        c3.metric("하루 평균 지출", f"{average_daily:,.0f}원")

        st.divider()
        st.subheader("카테고리별 소비")
        sorted_categories = dict(sorted(category_totals.items(), key=lambda item: item[1], reverse=True))
        st.bar_chart(sorted_categories)
        for cat, value in sorted_categories.items():
            st.write(f"- {cat}: {value:,}원 ({value / total_spending * 100:.1f}%)")

        st.divider()
        st.subheader("📈 월별 소비 변화")
        monthly_rows = cur.execute("""
            SELECT substr(expense_date, 1, 7), SUM(amount)
            FROM expenses GROUP BY substr(expense_date, 1, 7)
            ORDER BY substr(expense_date, 1, 7) DESC LIMIT 6
        """).fetchall()
        monthly_rows.reverse()
        if monthly_rows:
            st.bar_chart({m: v for m, v in monthly_rows})
            for m, v in monthly_rows:
                st.write(f"{m}: {v:,}원")

        st.divider()
        st.subheader("🗓️ 소비 달력")
        calendar_month = this_month if selected_month == "전체" else selected_month
        year, month = map(int, calendar_month.split("-"))
        daily_rows = cur.execute("""
            SELECT expense_date, SUM(amount) FROM expenses
            WHERE expense_date LIKE ? GROUP BY expense_date
        """, (calendar_month + "%",)).fetchall()
        daily_totals_month = {d: v for d, v in daily_rows}
        st.caption(f"{year}년 {month}월 소비 기록")
        weeks = calendar.monthcalendar(year, month)
        calendar_data = []
        for week in weeks:
            line = []
            for day in week:
                if day == 0:
                    line.append("")
                elif day in daily_totals_month:
                    line.append(f"{day}일\n{daily_totals_month[day]:,}원")
                else:
                    line.append(f"{day}일")
            calendar_data.append(line)
        st.table({
            "월": [w[0] for w in calendar_data], "화": [w[1] for w in calendar_data],
            "수": [w[2] for w in calendar_data], "목": [w[3] for w in calendar_data],
            "금": [w[4] for w in calendar_data], "토": [w[5] for w in calendar_data],
            "일": [w[6] for w in calendar_data]
        })

        st.divider()
        st.subheader("🔍 소비 패턴 분석")
        c1, c2, c3 = st.columns(3)
        c1.metric("가장 많이 쓴 항목", top_category)
        c2.metric("지출이 가장 많았던 날", highest_day)
        c3.metric("하루 평균 지출", f"{average_daily:,.0f}원")
        st.caption(f"{top_category}에 총 {category_totals[top_category]:,}원을 사용했어요.")
    else:
        st.info("분석할 소비 기록이 없습니다. 먼저 소비 기록을 추가해 주세요.")

# 월간 보고서
elif menu == "월간 보고서":
    st.header("📑 나의 소비 보고서")
    month_options = sorted({r[1][:7] for r in all_rows}, reverse=True)
    if month_options:
        selected_month = st.selectbox("보고서를 만들 월", month_options, key="report_month")
        rows = [r for r in all_rows if r[1].startswith(selected_month)]
        report_total = sum(r[2] for r in rows)
        report_categories = {}
        for r in rows:
            report_categories[r[3]] = report_categories.get(r[3], 0) + r[2]

        top_category = max(report_categories, key=report_categories.get)
        spending_days = len({r[1] for r in rows})
        average_daily = report_total / spending_days

        st.markdown(f"### 🗓️ {selected_month} 소비 리포트")
        c1, c2, c3 = st.columns(3)
        c1.metric("총지출", f"{report_total:,}원")
        c2.metric("최다 지출 항목", top_category)
        c3.metric("하루 평균", f"{average_daily:,.0f}원")

        st.subheader("카테고리별 소비 현황")
        sorted_report = sorted(report_categories.items(), key=lambda item: item[1], reverse=True)
        for cat, value in sorted_report:
            st.write(f"- {cat}: {value:,}원 ({value / report_total * 100:.1f}%)")

        report_text = (
            f"{selected_month} MONEY:LOG 소비 보고서\n\n"
            f"총지출: {report_total:,}원\n"
            f"가장 많이 지출한 항목: {top_category}\n"
            f"하루 평균 지출: {average_daily:,.0f}원\n\n"
            "카테고리별 지출:\n"
            + "\n".join(
                f"{cat}: {value:,}원 ({value / report_total * 100:.1f}%)"
                for cat, value in sorted_report
            )
        )
        st.download_button(
            "📥 소비 보고서 다운로드", data=report_text,
            file_name=f"MONEY_LOG_{selected_month}_보고서.txt", mime="text/plain"
        )
    else:
        st.info("소비 기록을 입력하면 월간 보고서를 만들 수 있어요.")

conn.close()
