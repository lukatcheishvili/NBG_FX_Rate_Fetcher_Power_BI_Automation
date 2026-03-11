# 📊 NBG FX Rate Fetcher — Power BI Automation

> Automated National Bank of Georgia exchange rate integration for financial statement working files — no more manual lookups.

---

## 🧩 Overview

Every accountant or financial analyst at a Georgian bank knows the pain: open a browser, navigate to the [National Bank of Georgia (NBG)](https://nbg.gov.ge/en/monetary-policy/currency) website, look up the exchange rate for a specific date, paste it into your working file, repeat for every financial statement period.

**This project eliminates that workflow entirely.**

`NBG FX Rate Fetcher` is a Power BI report that connects directly to the NBG's public exchange rate data and surfaces the correct rate for any given date — ready to feed into your financial statement working files at JSC Bank of Georgia.

---

## 🚀 Features

- **Live NBG Rate Fetching** — Pulls exchange rates directly from the National Bank of Georgia data source
- **Date-Specific Lookups** — Select any date and instantly get the official NBG rate for that period
- **Multi-Currency Support** — Covers the major currencies used in financial statement reporting (USD, EUR, GBP, and more)
- **Financial Statement Ready** — Designed specifically for working file use cases: translation rates, closing rates, average rates
- **Zero Manual Entry** — No copy-pasting, no browser tabs, no human error

---

## 🏦 Use Case

When preparing financial statements at **JSC Bank of Georgia**, IFRS reporting and consolidation working files require exchange rates from the NBG for:

| Rate Type | Purpose |
|---|---|
| **Closing Rate** | Balance Sheet translation as at period end |
| **Average Rate** | P&L translation for the reporting period |
| **Transaction Date Rate** | Specific transaction-level conversions |

Previously, each of these required a manual lookup on the NBG website. This Power BI file handles it automatically.

---

## 📁 File Structure

```
NBG-FX-Rate-Fetcher/
│
├── Personal_Portfolio_-_NBG_Rates.pbix   # Main Power BI report file
└── README.md                             # You are here
```

---

## 🛠️ How to Use

1. **Open** `Personal_Portfolio_-_NBG_Rates.pbix` in Power BI Desktop
2. **Refresh** the data to pull the latest rates from NBG
3. **Select** your reporting date or date range using the date slicer
4. **Read off** the rate(s) needed for your working file
5. *(Optional)* Export or copy the rate directly into your Excel working file

> ⚠️ **Requirements:** Power BI Desktop (free) with internet access to reach the NBG data endpoint.

---

## 🌐 Data Source

All exchange rates are sourced from the **National Bank of Georgia's** official public API / data feed:

🔗 [https://nbg.gov.ge/en/monetary-policy/currency](https://nbg.gov.ge/en/monetary-policy/currency)

Rates are official, auditable, and consistent with what NBG publishes for regulatory and financial reporting purposes.

---

## 💡 Background & Motivation

This tool was built out of a real day-to-day frustration in financial reporting work. The NBG website works fine — but fetching rates manually for every statement, every period, every currency is repetitive and error-prone.

Power BI's data connectivity makes it trivial to automate this fetch, apply date logic, and surface exactly the rate you need — making working file preparation significantly faster and more reliable.

---

## 📌 Notes

- This is a **personal productivity project**, not an official tool of JSC Bank of Georgia
- Rates reflect NBG official published rates and may differ slightly from interbank or market rates
- Always verify critical rates against the NBG website for audit trail purposes

---

## 👤 Author

Built for personal use to support financial statement working files at **JSC Bank of Georgia**.

---

*If this saves you even 10 minutes per reporting period — it's done its job.*
