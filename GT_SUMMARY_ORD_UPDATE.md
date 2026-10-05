# GT ORD summary and template update

Summary and dealer reports now parse the full product lists and use the same final movement aggregation. Hanuman competitor lookup is case independent. GT uses the supplied ten-column Summary_beer layout, with region movement band counts. Total outlet counts remain internal for status logic. HORECA retains its existing layout.

Compare commands using the same dealer and report date: the supplied summary is October 3 while the supplied dealer report is September 26. This patch does not invent the example template counts or substitute NCP values for ORD. Genuine unavailability still produces zero.

Validation: 22 targeted tests passed and app compilation passed. Existing dependency deprecation warnings remain. Production Kobo values and Railway deployment were not verified here.
