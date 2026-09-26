import streamlit as st
import os
import json
from datetime import timedelta

st.set_page_config(page_title="Customer 360", page_icon=":busts_in_silhouette:", layout="wide")

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))


# --- cached data loaders ---
@st.cache_data(ttl="10m")
def load_customers():
    return conn.query("SELECT * FROM CUSTOMER360_DB.C360.CUSTOMERS")


@st.cache_data(ttl="10m")
def load_orders():
    return conn.query("SELECT * FROM CUSTOMER360_DB.C360.ORDERS")


@st.cache_data(ttl="10m")
def load_tickets():
    return conn.query("SELECT * FROM CUSTOMER360_DB.C360.SUPPORT_TICKETS")


@st.cache_data(ttl="10m")
def load_activity():
    return conn.query("SELECT * FROM CUSTOMER360_DB.C360.WEB_ACTIVITY")


# --- load data with spinner ---
with st.spinner("Loading Customer 360 data..."):
    customers = load_customers()
    orders = load_orders()
    tickets = load_tickets()
    activity = load_activity()

import pandas as pd
orders["ORDER_DATE"] = pd.to_datetime(orders["ORDER_DATE"])
tickets["CREATED_DATE"] = pd.to_datetime(tickets["CREATED_DATE"])
activity["EVENT_DATE"] = pd.to_datetime(activity["EVENT_DATE"])

# --- sidebar filters ---
with st.sidebar:
    st.title("Filters")

    segments = st.multiselect("Segment", sorted(customers["SEGMENT"].unique()), default=sorted(customers["SEGMENT"].unique()))
    regions = st.multiselect("Region", sorted(customers["REGION"].unique()), default=sorted(customers["REGION"].unique()))
    statuses = st.multiselect("Status", sorted(customers["STATUS"].unique()), default=sorted(customers["STATUS"].unique()))
    industries = st.multiselect("Industry", sorted(customers["INDUSTRY"].unique()), default=sorted(customers["INDUSTRY"].unique()))

    st.divider()
    if st.button("Clear cache", on_click=lambda: (load_customers.clear(), load_orders.clear(), load_tickets.clear(), load_activity.clear())):
        st.rerun()

# --- apply filters ---
mask = (
    customers["SEGMENT"].isin(segments)
    & customers["REGION"].isin(regions)
    & customers["STATUS"].isin(statuses)
    & customers["INDUSTRY"].isin(industries)
)
filtered = customers[mask]
customer_ids = set(filtered["CUSTOMER_ID"])
f_orders = orders[orders["CUSTOMER_ID"].isin(customer_ids)]
f_tickets = tickets[tickets["CUSTOMER_ID"].isin(customer_ids)]
f_activity = activity[activity["CUSTOMER_ID"].isin(customer_ids)]

# --- header ---
st.title("Customer 360 Dashboard")

# --- KPI row ---
total_customers = len(filtered)
total_revenue = f_orders[f_orders["ORDER_STATUS"] == "Completed"]["ORDER_AMOUNT"].sum()
avg_health = filtered["HEALTH_SCORE"].mean()
avg_nps = filtered["NPS_SCORE"].mean()
open_tickets = len(f_tickets[f_tickets["TICKET_STATUS"].isin(["Open", "In Progress"])])
avg_ltv = filtered["LIFETIME_VALUE"].mean()

with st.container(horizontal=True):
    st.metric("Total Customers", f"{total_customers:,}", border=True)
    st.metric("Revenue (Completed)", f"${total_revenue:,.0f}", border=True)
    st.metric("Avg Health Score", f"{avg_health:.0f}/100", border=True)
    st.metric("Avg NPS", f"{avg_nps:.1f}/10", border=True)
    st.metric("Open Tickets", f"{open_tickets:,}", border=True)
    st.metric("Avg LTV", f"${avg_ltv:,.0f}", border=True)

# --- tabs ---
tab_overview, tab_revenue, tab_support, tab_engagement, tab_detail, tab_chat = st.tabs(
    ["Overview", "Revenue", "Support", "Engagement", "Customer Detail", "Ask AI"],
    on_change="rerun",
)

# --- overview tab ---
if tab_overview.open:
    with tab_overview:
        col1, col2 = st.columns(2)
        with col1:
            with st.container(border=True):
                st.subheader("Customers by Status")
                status_counts = filtered["STATUS"].value_counts().reset_index()
                status_counts.columns = ["Status", "Count"]
                st.bar_chart(status_counts, x="Status", y="Count")

        with col2:
            with st.container(border=True):
                st.subheader("Customers by Segment")
                seg_counts = filtered["SEGMENT"].value_counts().reset_index()
                seg_counts.columns = ["Segment", "Count"]
                st.bar_chart(seg_counts, x="Segment", y="Count")

        col3, col4 = st.columns(2)
        with col3:
            with st.container(border=True):
                st.subheader("Customers by Region")
                reg_counts = filtered["REGION"].value_counts().reset_index()
                reg_counts.columns = ["Region", "Count"]
                st.bar_chart(reg_counts, x="Region", y="Count")

        with col4:
            with st.container(border=True):
                st.subheader("Customers by Industry")
                ind_counts = filtered["INDUSTRY"].value_counts().reset_index()
                ind_counts.columns = ["Industry", "Count"]
                st.bar_chart(ind_counts, x="Industry", y="Count")

        with st.container(border=True):
            st.subheader("Health Score Distribution")
            health_bins = filtered["HEALTH_SCORE"].value_counts(bins=10).sort_index().reset_index()
            health_bins.columns = ["Score Range", "Count"]
            health_bins["Score Range"] = health_bins["Score Range"].astype(str)
            st.bar_chart(health_bins, x="Score Range", y="Count")

# --- revenue tab ---
if tab_revenue.open:
    with tab_revenue:
        completed = f_orders[f_orders["ORDER_STATUS"] == "Completed"].copy()

        col1, col2 = st.columns(2)
        with col1:
            with st.container(border=True):
                st.subheader("Monthly Revenue Trend")
                if not completed.empty:
                    completed["MONTH"] = completed["ORDER_DATE"].dt.to_period("M").astype(str)
                    monthly = completed.groupby("MONTH")["ORDER_AMOUNT"].sum().reset_index()
                    monthly.columns = ["Month", "Revenue"]
                    st.line_chart(monthly, x="Month", y="Revenue")
                else:
                    st.info("No completed orders for selected filters.")

        with col2:
            with st.container(border=True):
                st.subheader("Revenue by Product Category")
                if not completed.empty:
                    cat_rev = completed.groupby("PRODUCT_CATEGORY")["ORDER_AMOUNT"].sum().reset_index()
                    cat_rev.columns = ["Category", "Revenue"]
                    st.bar_chart(cat_rev, x="Category", y="Revenue")
                else:
                    st.info("No completed orders for selected filters.")

        col3, col4 = st.columns(2)
        with col3:
            with st.container(border=True):
                st.subheader("Order Status Breakdown")
                os_counts = f_orders["ORDER_STATUS"].value_counts().reset_index()
                os_counts.columns = ["Status", "Count"]
                st.bar_chart(os_counts, x="Status", y="Count")

        with col4:
            with st.container(border=True):
                st.subheader("Top 10 Customers by Revenue")
                if not completed.empty:
                    top_cust = completed.groupby("CUSTOMER_ID")["ORDER_AMOUNT"].sum().nlargest(10).reset_index()
                    top_cust = top_cust.merge(
                        filtered[["CUSTOMER_ID", "FIRST_NAME", "LAST_NAME"]],
                        on="CUSTOMER_ID",
                        how="left",
                    )
                    top_cust["Customer"] = top_cust["FIRST_NAME"] + " " + top_cust["LAST_NAME"]
                    st.dataframe(
                        top_cust[["Customer", "ORDER_AMOUNT"]].rename(columns={"ORDER_AMOUNT": "Total Revenue"}),
                        hide_index=True,
                        use_container_width=True,
                    )
                else:
                    st.info("No completed orders for selected filters.")

# --- support tab ---
if tab_support.open:
    with tab_support:
        col1, col2 = st.columns(2)
        with col1:
            with st.container(border=True):
                st.subheader("Tickets by Priority")
                pri_counts = f_tickets["PRIORITY"].value_counts().reset_index()
                pri_counts.columns = ["Priority", "Count"]
                st.bar_chart(pri_counts, x="Priority", y="Count")

        with col2:
            with st.container(border=True):
                st.subheader("Tickets by Category")
                cat_counts = f_tickets["CATEGORY"].value_counts().reset_index()
                cat_counts.columns = ["Category", "Count"]
                st.bar_chart(cat_counts, x="Category", y="Count")

        col3, col4 = st.columns(2)
        with col3:
            with st.container(border=True):
                st.subheader("Ticket Status")
                ts_counts = f_tickets["TICKET_STATUS"].value_counts().reset_index()
                ts_counts.columns = ["Status", "Count"]
                st.bar_chart(ts_counts, x="Status", y="Count")

        with col4:
            with st.container(border=True):
                st.subheader("Avg Resolution Time by Priority")
                resolved = f_tickets[f_tickets["TICKET_STATUS"].isin(["Resolved", "Closed"])]
                if not resolved.empty:
                    avg_res = resolved.groupby("PRIORITY")["RESOLUTION_HOURS"].mean().reset_index()
                    avg_res.columns = ["Priority", "Avg Hours"]
                    st.bar_chart(avg_res, x="Priority", y="Avg Hours")
                else:
                    st.info("No resolved tickets for selected filters.")

        with st.container(border=True):
            st.subheader("Monthly Ticket Volume")
            if not f_tickets.empty:
                f_tickets_copy = f_tickets.copy()
                f_tickets_copy["MONTH"] = f_tickets_copy["CREATED_DATE"].dt.to_period("M").astype(str)
                monthly_tickets = f_tickets_copy.groupby("MONTH").size().reset_index(name="Count")
                st.line_chart(monthly_tickets, x="MONTH", y="Count")
            else:
                st.info("No tickets for selected filters.")

# --- engagement tab ---
if tab_engagement.open:
    with tab_engagement:
        col1, col2 = st.columns(2)
        with col1:
            with st.container(border=True):
                st.subheader("Activity by Event Type")
                ev_counts = f_activity["EVENT_TYPE"].value_counts().reset_index()
                ev_counts.columns = ["Event Type", "Count"]
                st.bar_chart(ev_counts, x="Event Type", y="Count")

        with col2:
            with st.container(border=True):
                st.subheader("Daily Active Users (Last 90 Days)")
                if not f_activity.empty:
                    dau = f_activity.groupby("EVENT_DATE")["CUSTOMER_ID"].nunique().reset_index()
                    dau.columns = ["Date", "Active Users"]
                    st.line_chart(dau.sort_values("Date"), x="Date", y="Active Users")
                else:
                    st.info("No activity for selected filters.")

        col3, col4 = st.columns(2)
        with col3:
            with st.container(border=True):
                st.subheader("Avg Session Duration by Event")
                if not f_activity.empty:
                    avg_dur = f_activity.groupby("EVENT_TYPE")["SESSION_DURATION_MIN"].mean().reset_index()
                    avg_dur.columns = ["Event Type", "Avg Duration (min)"]
                    st.bar_chart(avg_dur, x="Event Type", y="Avg Duration (min)")
                else:
                    st.info("No activity for selected filters.")

        with col4:
            with st.container(border=True):
                st.subheader("Weekly Engagement Trend")
                if not f_activity.empty:
                    act_copy = f_activity.copy()
                    act_copy["WEEK"] = act_copy["EVENT_DATE"].dt.to_period("W").astype(str)
                    weekly = act_copy.groupby("WEEK").size().reset_index(name="Events")
                    st.line_chart(weekly.sort_values("WEEK"), x="WEEK", y="Events")
                else:
                    st.info("No activity for selected filters.")

# --- customer detail tab ---
if tab_detail.open:
    with tab_detail:
        search = st.text_input("Search customer by name")
        display = filtered.copy()
        if search:
            search_lower = search.lower()
            display = display[
                display["FIRST_NAME"].str.lower().str.contains(search_lower, na=False)
                | display["LAST_NAME"].str.lower().str.contains(search_lower, na=False)
            ]

        selected_idx = st.dataframe(
            display[["CUSTOMER_ID", "FIRST_NAME", "LAST_NAME", "SEGMENT", "INDUSTRY", "REGION", "STATUS", "HEALTH_SCORE", "NPS_SCORE", "LIFETIME_VALUE"]],
            hide_index=True,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
        )

        rows = selected_idx.selection.rows
        if rows:
            cust = display.iloc[rows[0]]
            cid = cust["CUSTOMER_ID"]

            st.subheader(f"{cust['FIRST_NAME']} {cust['LAST_NAME']}")

            with st.container(horizontal=True):
                st.metric("Segment", cust["SEGMENT"], border=True)
                st.metric("Industry", cust["INDUSTRY"], border=True)
                st.metric("Region", cust["REGION"], border=True)
                st.metric("Status", cust["STATUS"], border=True)
                st.metric("Health", f"{cust['HEALTH_SCORE']}/100", border=True)
                st.metric("NPS", f"{cust['NPS_SCORE']}/10", border=True)
                st.metric("LTV", f"${cust['LIFETIME_VALUE']:,.0f}", border=True)

            c_orders = f_orders[f_orders["CUSTOMER_ID"] == cid].sort_values("ORDER_DATE", ascending=False)
            c_tickets = f_tickets[f_tickets["CUSTOMER_ID"] == cid].sort_values("CREATED_DATE", ascending=False)
            c_activity = f_activity[f_activity["CUSTOMER_ID"] == cid].sort_values("EVENT_DATE", ascending=False)

            col1, col2, col3 = st.columns(3)
            with col1:
                with st.container(border=True):
                    st.markdown(f"**Orders** ({len(c_orders)})")
                    if not c_orders.empty:
                        st.dataframe(
                            c_orders[["ORDER_DATE", "ORDER_AMOUNT", "ORDER_STATUS", "PRODUCT_CATEGORY"]],
                            hide_index=True,
                            use_container_width=True,
                        )
                    else:
                        st.caption("No orders")

            with col2:
                with st.container(border=True):
                    st.markdown(f"**Support Tickets** ({len(c_tickets)})")
                    if not c_tickets.empty:
                        st.dataframe(
                            c_tickets[["CREATED_DATE", "TICKET_STATUS", "PRIORITY", "CATEGORY"]],
                            hide_index=True,
                            use_container_width=True,
                        )
                    else:
                        st.caption("No tickets")

            with col3:
                with st.container(border=True):
                    st.markdown(f"**Recent Activity** ({len(c_activity)})")
                    if not c_activity.empty:
                        st.dataframe(
                            c_activity[["EVENT_DATE", "EVENT_TYPE", "SESSION_DURATION_MIN"]].head(20),
                            hide_index=True,
                            use_container_width=True,
                        )
                    else:
                        st.caption("No activity")

# --- ask AI tab ---
if tab_chat.open:
    with tab_chat:
        st.subheader("Ask AI about your customers")

        # build data context for the LLM
        status_summary = filtered["STATUS"].value_counts().to_dict()
        segment_summary = filtered["SEGMENT"].value_counts().to_dict()
        region_summary = filtered["REGION"].value_counts().to_dict()
        industry_summary = filtered["INDUSTRY"].value_counts().to_dict()
        product_rev = (
            f_orders[f_orders["ORDER_STATUS"] == "Completed"]
            .groupby("PRODUCT_CATEGORY")["ORDER_AMOUNT"]
            .sum()
            .to_dict()
        )
        ticket_cat = f_tickets["CATEGORY"].value_counts().to_dict()
        ticket_pri = f_tickets["PRIORITY"].value_counts().to_dict()

        DATA_CONTEXT = f"""You are a Customer 360 AI analyst. Answer questions using ONLY the data context below.
Be concise and use numbers. If the data doesn't cover the question, say so.

CURRENT DASHBOARD METRICS (filtered view):
- Total customers: {total_customers}
- Total revenue (completed orders): ${total_revenue:,.0f}
- Average health score: {avg_health:.0f}/100
- Average NPS: {avg_nps:.1f}/10
- Open support tickets: {open_tickets}
- Average lifetime value: ${avg_ltv:,.0f}

CUSTOMER STATUS DISTRIBUTION: {status_summary}
CUSTOMER SEGMENTS: {segment_summary}
CUSTOMER REGIONS: {region_summary}
CUSTOMER INDUSTRIES: {industry_summary}

REVENUE BY PRODUCT CATEGORY (completed orders): {product_rev}

SUPPORT TICKET CATEGORIES: {ticket_cat}
SUPPORT TICKET PRIORITIES: {ticket_pri}

TABLES AVAILABLE:
- CUSTOMER360_DB.C360.CUSTOMERS (500 rows): CUSTOMER_ID, FIRST_NAME, LAST_NAME, SEGMENT, INDUSTRY, REGION, STATUS, SIGNUP_DATE, LIFETIME_VALUE, HEALTH_SCORE, NPS_SCORE
- CUSTOMER360_DB.C360.ORDERS (3000 rows): ORDER_ID, CUSTOMER_ID, ORDER_DATE, ORDER_AMOUNT, ORDER_STATUS, PRODUCT_CATEGORY
- CUSTOMER360_DB.C360.SUPPORT_TICKETS (1200 rows): TICKET_ID, CUSTOMER_ID, CREATED_DATE, TICKET_STATUS, PRIORITY, CATEGORY, RESOLUTION_HOURS
- CUSTOMER360_DB.C360.WEB_ACTIVITY (10000 rows): EVENT_ID, CUSTOMER_ID, EVENT_DATE, EVENT_TYPE, SESSION_DURATION_MIN
"""

        SUGGESTIONS = {
            ":blue[:material/trending_up:] Which segment has the highest revenue?": "Which customer segment generates the most revenue?",
            ":orange[:material/warning:] Who are the at-risk customers?": "How many at-risk customers are there and what are their characteristics?",
            ":green[:material/support_agent:] Summarize support ticket trends": "Summarize the support ticket trends by category and priority.",
            ":violet[:material/analytics:] Give me a full executive summary": "Give me a concise executive summary of the customer 360 data including revenue, health, engagement, and support metrics.",
        }

        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = []

        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        if not st.session_state.chat_messages:
            selected = st.pills("Try asking:", list(SUGGESTIONS.keys()), label_visibility="collapsed")
            if selected:
                st.session_state.chat_messages.append({"role": "user", "content": SUGGESTIONS[selected]})
                st.rerun()

        if prompt := st.chat_input("Ask about your customers..."):
            st.session_state.chat_messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.write(prompt)

            with st.chat_message("assistant"):
                messages = [{"role": "system", "content": DATA_CONTEXT}]
                for m in st.session_state.chat_messages:
                    messages.append({"role": m["role"], "content": m["content"]})

                session = conn.session()
                messages_json = json.dumps(messages)
                result = session.sql(
                    "SELECT SNOWFLAKE.CORTEX.COMPLETE('claude-3-5-sonnet', PARSE_JSON(:messages)) AS RESPONSE",
                    params={"messages": messages_json},
                ).collect()
                response = result[0]["RESPONSE"]
                st.write(response)

            st.session_state.chat_messages.append({"role": "assistant", "content": response})
