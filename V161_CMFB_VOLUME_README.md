# CMFB daily NCP volume export

New commands:

```text
/summary_volume_date 2026-11-04
/summary_volume_date GT 2026-11-04
/summary_volume_date HORECA 2026-11-04
```

A date alone includes GT and HORECA. The command returns exactly two sheets:

- `Summary_Volume`: all 65 official dealers, outlet-visit counts, CB LITE NCP, WURKZ NCP, DAZZ NCP, EXPREZ Can 330ml NCP, IZE COLA 500ml NCP, total volume, regional subtotals and grand total.
- `Detail_Volume`: Date, Region, Dealer, Outlet Name, Phone Number, Lat, Lon, Open Map, the five product volumes and total volume. Phone numbers stay as text. Valid coordinates have clickable Google Maps links.

All quantities use cartons (ctn), matching the Kobo fields. One row is one visit submission, not a deduplicated unique outlet. Final-summary control submissions are excluded. Blank quantities stay blank in detail; explicit zero stays zero; not-sold hidden quantities do not count. Each subtotal sums the detail visits. Unknown dealer codes, if returned by Kobo, remain visible after official dealers rather than disappearing.

The shared fast HORECA parser now retains the five NCP volume products so the HORECA CB LITE NCP field is available to the command. It continues to use the existing date-filtered Kobo fetch and caches; no full-history database sync is introduced.

CMFB replaces visible KB branding in the bot, API titles, XLSForm display title and existing report-template titles. The existing `/summary GT ...` and HORECA summary exports now embed the Chip Mong FoodBev logo. Existing field names, form_id, database keys, environment names and old template filenames remain compatible. The form to deploy is `templates/CMFB_Market_Improvement_XLSForm_GT_HORECA.xlsx`. Old Kobo template filenames contain the same branded form for existing scripts.

## Git Bash (existing repository)

Use the compact update ZIP for an existing installation. First make sure your current changes are committed or safely saved, and bring your branch up to date. Stop if Git reports conflicts.

```bash
cd /d/Bot/Market_Survey_Git
git status
git pull --rebase --autostash origin main
unzip -o ~/Downloads/CMFB_Market_Survey_V161_UPDATE.zip -d .
python verify_v161_volume_summary.py
python verify_v160_report_layout.py
python verify_v157_ncp_volume.py
python scripts/stage_v161.py
git diff --cached --stat
git commit -m "Add CMFB NCP daily volume summary and branding"
git push origin main
```

The full project ZIP is also supplied for a separate complete checkout. It contains the existing application source, templates and older fixes; generated exports, cached files and old test databases are excluded. Do not extract the full ZIP over a repository that has newer local work; apply the compact update instead.

After Railway deploys, use the commands above. For Kobo, replace the form in the existing project with the CMFB XLSX and Deploy. Keep the existing asset UID and API credentials. Git push alone does not replace the live Kobo form.

## Validation

The included offline checks run the production parser/report functions with synthetic data and isolated I/O. They cover nested GT/HORECA Kobo fields, command date/type selection, exactly two output sheets, five-product totals, all 65 dealers, decimals, zero and blank quantities, hidden not-sold quantities, summary exclusion, phone numbers, map links, logo embedding, the existing summary logo and preservation of Kobo field requirements. The existing V160 and V157 checks also pass. Layout previews were visually reviewed. No live Kobo credentials, Telegram send or Railway deployment was exercised here.
