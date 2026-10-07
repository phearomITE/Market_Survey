# GT summary availability coverage and missing outlet detail

Summary_beer has 15 columns matching the updated reference. District, Commune and Village counts are distinct areas among ordinary visits with CB LITE ORD available. Set unions deduplicate shared areas at region and overall levels. Final-summary records remain excluded from all visit and coverage counts.

CB LITE ORD Outlet uses existing availability rules. GB SNOW ORD Outlet is separately counted using the existing competitor rule (positive submitted movement score); it is not copied from CB LITE ORD. Counts are visits, not deduplicated physical shops.

Location_no_CB_LITE includes ordinary visits without CB LITE ORD availability. Columns: Date, Region, Dealer, Outlet Name, Phone, Province, District, Commune, Latitude, Longitude, Link Map, Status. Status is No, including missing availability under existing report rules. Valid GPS produces clickable Open Map. Blank GPS stays blank. Final-summary records never enter this sheet.

Village limitation: the bundled boundary dataset only resolves province, district and commune. Fast Kobo parsing now retains village/village_name/village_text when supplied. Villages are counted by resolved commune plus village name. Missing or unresolved village data is uncounted; commune totals are never copied into Village. Add accurate village source data to obtain complete village totals.

Region Total text remains bold red. HORECA layout remains unchanged. Previous ORD parser and calculation fixes are bundled. Tests: 30 targeted tests passed; compilation passed. Existing deprecation warnings remain. Live Railway and Kobo data were not verified here.
