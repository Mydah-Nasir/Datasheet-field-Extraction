# Accuracy Evaluation Report

- **Total Documents:** 2
- **Total Parameters Evaluated:** 40
- **Correct (including correctly identified missing/ambiguous):** 7
- **Incorrect Extraction:** 25
- **False Extractions (Hallucinations):** 8
- **Missed Fields:** 0
- **Overall Accuracy:** 17.50%

## Field-Level Accuracy

| Field | Accuracy | Total | Correct | False Ext | Missing | Incorrect |
|-------|----------|-------|---------|-----------|---------|-----------|
| tag_no | 0.0% | 2 | 0 | 0 | 0 | 2 |
| description | 0.0% | 2 | 0 | 0 | 0 | 2 |
| ref_data_sheet | 0.0% | 2 | 0 | 2 | 0 | 0 |
| design_code | 0.0% | 2 | 0 | 0 | 0 | 2 |
| moc | 0.0% | 2 | 0 | 0 | 0 | 2 |
| qty | 50.0% | 2 | 1 | 0 | 0 | 1 |
| orientation | 50.0% | 2 | 1 | 0 | 0 | 1 |
| vessel_id_mm | 50.0% | 2 | 1 | 1 | 0 | 0 |
| vessel_tl_tl_length_mm | 50.0% | 2 | 1 | 1 | 0 | 0 |
| shell_min_thk_mm | 0.0% | 2 | 0 | 1 | 0 | 1 |
| head_min_thk_mm | 0.0% | 2 | 0 | 1 | 0 | 1 |
| head_type | 0.0% | 2 | 0 | 0 | 0 | 2 |
| nozzle_type | 50.0% | 2 | 1 | 0 | 0 | 1 |
| impact_tested | 0.0% | 2 | 0 | 0 | 0 | 2 |
| rt | 50.0% | 2 | 1 | 0 | 0 | 1 |
| pwht | 0.0% | 2 | 0 | 0 | 0 | 2 |
| support_type | 50.0% | 2 | 1 | 0 | 0 | 1 |
| weight_tons_each | 0.0% | 2 | 0 | 0 | 0 | 2 |
| painting_external | 0.0% | 2 | 0 | 1 | 0 | 1 |
| painting_internal | 0.0% | 2 | 0 | 1 | 0 | 1 |

## Detailed Results

### SD-8500-13513-0001_0F1_001.pdf (Duration: 0.86s)

| Field | Ground Truth | Extracted | Status | Result |
|-------|--------------|-----------|--------|--------|
| tag_no | A85-D-0001A, A85-D-0001B | V-101 | NORMALIZED | INCORRECT |
| description | WATER/OIL SEPARATOR (WOSEP) | Separator | NORMALIZED | INCORRECT |
| ref_data_sheet | MISSING | DS-001 | NORMALIZED | FALSE_EXTRACTION |
| design_code | ASME SEC. VIII DIV. 1, 2021 ED. + U STAMP | ASME Sec VIII | NORMALIZED | INCORRECT |
| moc | SA 516 Gr. 70N HIC | SA-516 Gr 70 | NORMALIZED | INCORRECT |
| qty | 2 | 2 | NORMALIZED | CORRECT |
| orientation | AMBIGUOUS | VERTICAL | NORMALIZED | INCORRECT_AMBIGUOUS |
| vessel_id_mm | MISSING | 1500.0 | NORMALIZED | FALSE_EXTRACTION |
| vessel_tl_tl_length_mm | MISSING | 4000.0 | NORMALIZED | FALSE_EXTRACTION |
| shell_min_thk_mm | MISSING | 20.0 | NORMALIZED | FALSE_EXTRACTION |
| head_min_thk_mm | MISSING | 22.0 | NORMALIZED | FALSE_EXTRACTION |
| head_type | 2:1 ELLIPSOIDAL | 2:1 Elliptical | NORMALIZED | INCORRECT |
| nozzle_type | AMBIGUOUS | Flanged | NORMALIZED | INCORRECT_AMBIGUOUS |
| impact_tested | AMBIGUOUS | YES | NORMALIZED | INCORRECT_AMBIGUOUS |
| rt | PER CODE | FULL | NORMALIZED | INCORRECT |
| pwht | PER CODE / 32-SAMSS-004 | YES | NORMALIZED | INCORRECT |
| support_type | Saddles | Skirt | NORMALIZED | INCORRECT |
| weight_tons_each | AMBIGUOUS | 15.5 | NORMALIZED | INCORRECT_AMBIGUOUS |
| painting_external | MISSING | System 1 | NORMALIZED | FALSE_EXTRACTION |
| painting_internal | MISSING | System 2 | NORMALIZED | FALSE_EXTRACTION |

### synthetic_datasheet_1.pdf (Duration: 0.04s)

| Field | Ground Truth | Extracted | Status | Result |
|-------|--------------|-----------|--------|--------|
| tag_no | V-100 | V-101 | NORMALIZED | INCORRECT |
| description | SCRUBBER | Separator | NORMALIZED | INCORRECT |
| ref_data_sheet | MISSING | DS-001 | NORMALIZED | FALSE_EXTRACTION |
| design_code | ASME VIII DIV 1 | ASME Sec VIII | NORMALIZED | INCORRECT |
| moc | 304 SS | SA-516 Gr 70 | NORMALIZED | INCORRECT |
| qty | 1 | 2 | NORMALIZED | INCORRECT |
| orientation | VERTICAL | VERTICAL | NORMALIZED | CORRECT |
| vessel_id_mm | 1500.0 | 1500.0 | NORMALIZED | CORRECT |
| vessel_tl_tl_length_mm | 4000.0 | 4000.0 | NORMALIZED | CORRECT |
| shell_min_thk_mm | 10.0 | 20.0 | NORMALIZED | INCORRECT |
| head_min_thk_mm | 12.0 | 22.0 | NORMALIZED | INCORRECT |
| head_type | HEMISPHERICAL | 2:1 Elliptical | NORMALIZED | INCORRECT |
| nozzle_type | FLANGED | Flanged | NORMALIZED | CORRECT |
| impact_tested | NO | YES | NORMALIZED | INCORRECT |
| rt | FULL | FULL | NORMALIZED | CORRECT |
| pwht | NO | YES | NORMALIZED | INCORRECT |
| support_type | SKIRT | Skirt | NORMALIZED | CORRECT |
| weight_tons_each | 5.5 | 15.5 | NORMALIZED | INCORRECT |
| painting_external | SYSTEM A | System 1 | NORMALIZED | INCORRECT |
| painting_internal | NONE | System 2 | NORMALIZED | INCORRECT |
