# CropShield AI — Business Model Canvas

**Status:** Hypotheses for pilot discovery; none of the blocks below are validated.  
**Rule:** No market-size, pricing, revenue, or adoption figures are assumed.

**Current product evidence:** this is a work-in-progress prototype, not a
deployed service or validated pilot. There is no active model artifact in the
current `models/` directory; the model remains gated and has not been retrained.
The synthetic browser fixtures and demo data establish neither user demand nor
field accuracy. No customer, revenue, operating-cost, or environmental-impact
metric is currently established.

| Business Model Canvas block | CropShield AI hypothesis |
|---|---|
| **1. Customer segments** | **Hypothesis:** State agriculture departments and extension services may need to prioritise field visits across a district/region. **Hypothesis:** Farmer Producer Organisations (FPOs) and cooperatives may want shared crop-monitoring support. **Hypothesis:** Agri-insurers may use field-level signals as an additional review input, not as an automated claim decision. **Hypothesis:** Cooperative banks may value an optional monitoring signal for portfolio support, subject to consent and governance. **Hypothesis:** NGOs and agri-input companies may use regional monitoring to support field teams, provided alerts are not marketed as diagnoses. |
| **2. Value propositions** | **Hypothesis:** A ranked inspection queue can help officers allocate limited inspection capacity. **Hypothesis:** Per-field historical baselines, persistence, confidence, rain context, and visible evidence can be more actionable than viewing a single NDVI image. **Hypothesis:** Marathi/Hindi explanations can make the output more accessible to farmers. CropShield remains an inspection aid, not a crop-loss predictor or causal diagnosis. |
| **3. Channels** | **Hypothesis:** Pilot through district/state extension programmes, KVK/university field networks, FPO/cooperative partners, and NGO programmes. A hosted web application and partner-led onboarding may suit operational teams. Validate channel access and procurement requirements before investment. |
| **4. Customer relationships** | **Hypothesis:** Early institutional customers will require assisted onboarding, region/season setup, training, support, and periodic review of threshold/validation reports. Farmer-facing use may require local-language facilitation and a clear human follow-up path. |
| **5. Revenue streams** | **Hypothesis:** Institutional subscription per district/season. **Hypothesis:** Per-hectare monitoring fee. **Hypothesis:** Grant-funded pilots. **Hypothesis:** API/data licensing under suitable data rights, privacy, and governance. No prices, contract values, or revenue forecasts are assumed. |
| **6. Key resources** | **Hypothesis:** Reliable public satellite and rainfall data; Earth Engine access; field boundary datasets; validated pipeline and parameter history; secure backend/database; usable map and translations; field-validation relationships; domain, remote-sensing, engineering, and local-language expertise. |
| **7. Key activities** | **Hypothesis:** Configure and run seasonal extraction; maintain quality checks and baseline/anomaly pipeline; measure validation performance; support region/field data onboarding; provide and maintain the application; train users; collect consented field feedback; review alert wording and translations. |
| **8. Key partnerships** | **Hypothesis:** Google Earth Engine and Copernicus/public data providers enable data access. Agricultural universities and Krishi Vigyan Kendras (KVKs) may support agronomic review and field validation. Local-language partners may review Marathi/Hindi copy and read-aloud UX. FPOs/cooperatives, extension services, and NGOs may support pilot recruitment and feedback. |
| **9. Cost structure** | **Hypothesis:** Cloud/backend/database hosting and Earth Engine usage; data cleaning and boundary preparation; field validation and travel; language review and accessibility testing; onboarding, training, and support; software maintenance and security; partner coordination. Cost drivers and actual costs remain to be measured. |

## Validation plan

Test the central buyer/user assumption first: **will extension officers use a field-level, evidence-backed queue to change which fields they inspect, and will they trust the confidence and caveats?**

1. Interview extension officers and observe their existing prioritisation workflow before showing the product.
2. Walk through a clearly labelled synthetic map and field detail; ask participants to explain an alert and `cannot_assess` in their own words.
3. Run a consented, bounded pilot with a chosen region only after source data and field boundaries are approved. Compare recommendations with field observations; use `pipeline/validate.py` for algorithmic metrics and keep user feedback distinct from model validation.
4. Ask the institution who owns procurement, data governance, support, and seasonal renewal decisions.
5. Test the farmer-facing Marathi/Hindi explanation with local-language reviewers and farmers before treating translation as complete.
6. Only after willingness-to-use and operating costs are better understood, test which proposed funding/revenue model is acceptable. Do not test willingness to pay with invented price anchors.