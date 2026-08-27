# NRCS Version 9.3 indicator implementation report

## Scope and safeguards

This is an indicator-evidence implementation, not a final hydric/nonhydric classification. It uses only approved Version 9.3 indicators in the primary analysis. Dry colors, horizon `g` suffixes, chemistry, and MIR were not used as indicator evidence. Missing observations remain unknown. The February 2026 errata were reviewed; its Version 9.3 corrections to the 15-cm chroma-zone wording do not relax any rule here.

The executable first pass is deliberately limited to A1, A10, A11, A12, A3, A7, A8, A9, F2, F3, F6, F7, S4, S5. Even these are marked partially evaluable at the dataset level because the NASIS render is incomplete for some pedons. A result of `INDICATOR_NOT_DEMONSTRATED` is not a nonhydric label.

## Spatial assignment

- Pedon rows: 777
- Point within official MLRA polygon: 771
- Missing coordinates: 6
- No polygon match: 0
- Source: USDA NRCS 2022 MLRA Geographic Database, version 5.2 (MLRA_52)

## Coverage metrics

| indicator | name                         | geographically_applicable | fully_evaluable | partially_evaluable | not_evaluable | present | not_demonstrated | insufficient_information |
| --------- | ---------------------------- | ------------------------- | --------------- | ------------------- | ------------- | ------- | ---------------- | ------------------------ |
| A1        | Histosol or Histel           | 719                       | 0               | 719                 | 0             | 0       | 709              | 10                       |
| A2        | Histic Epipedon              | 719                       | 0               | 0                   | 719           | 0       | 0                | 719                      |
| A3        | Black Histic                 | 719                       | 0               | 719                 | 0             | 0       | 26               | 693                      |
| A4        | Hydrogen Sulfide             | 719                       | 0               | 0                   | 719           | 0       | 0                | 719                      |
| A5        | Stratified Layers            | 385                       | 0               | 0                   | 385           | 0       | 0                | 385                      |
| A6        | Organic Bodies               | 171                       | 0               | 0                   | 171           | 0       | 0                | 171                      |
| A7        | 5 cm Mucky Mineral           | 171                       | 0               | 171                 | 0             | 8       | 7                | 156                      |
| A8        | Muck Presence                | 90                        | 0               | 90                  | 0             | 0       | 6                | 84                       |
| A9        | 1 cm Muck                    | 301                       | 0               | 301                 | 0             | 0       | 10               | 291                      |
| A10       | 2 cm Muck                    | 81                        | 0               | 81                  | 0             | 0       | 0                | 81                       |
| A11       | Depleted Below Dark Surface  | 678                       | 0               | 678                 | 0             | 0       | 8                | 670                      |
| A12       | Thick Dark Surface           | 719                       | 0               | 719                 | 0             | 0       | 8                | 711                      |
| A13       | Alaska Gleyed                | 41                        | 0               | 0                   | 41            | 0       | 0                | 41                       |
| A14       | Alaska Redox                 | 41                        | 0               | 0                   | 41            | 0       | 0                | 41                       |
| A15       | Alaska Gleyed Pores          | 41                        | 0               | 0                   | 41            | 0       | 0                | 41                       |
| A16       | Coast Prairie Redox          | 0                         | 0               | 0                   | 0             | 0       | 0                | 0                        |
| A17       | Mesic Spodic                 | 17                        | 0               | 0                   | 17            | 0       | 0                | 17                       |
| A18       | Iron Monosulfide             | 719                       | 0               | 0                   | 719           | 0       | 0                | 719                      |
| S1        | Sandy Mucky Mineral          | 599                       | 0               | 0                   | 599           | 0       | 0                | 599                      |
| S2        | 2.5 cm Mucky Peat or Peat    | 82                        | 0               | 0                   | 82            | 0       | 0                | 82                       |
| S3        | 5 cm Mucky Peat or Peat      | 67                        | 0               | 0                   | 67            | 0       | 0                | 67                       |
| S4        | Sandy Gleyed Matrix          | 678                       | 0               | 678                 | 0             | 0       | 232              | 446                      |
| S5        | Sandy Redox                  | 667                       | 0               | 667                 | 0             | 0       | 59               | 608                      |
| S6        | Stripped Matrix              | 667                       | 0               | 0                   | 667           | 0       | 0                | 667                      |
| S7        | Dark Surface                 | 285                       | 0               | 0                   | 285           | 0       | 0                | 285                      |
| S8        | Polyvalue Below Surface      | 113                       | 0               | 0                   | 113           | 0       | 0                | 113                      |
| S9        | Thin Dark Surface            | 113                       | 0               | 0                   | 113           | 0       | 0                | 113                      |
| S11       | High Chroma Sands            | 41                        | 0               | 0                   | 41            | 0       | 0                | 41                       |
| S12       | Barrier Islands 1 cm Muck    | 0                         | 0               | 0                   | 0             | 0       | 0                | 0                        |
| F1        | Loamy Mucky Mineral          | 361                       | 0               | 0                   | 361           | 0       | 0                | 361                      |
| F2        | Loamy Gleyed Matrix          | 678                       | 0               | 678                 | 0             | 1       | 231              | 446                      |
| F3        | Depleted Matrix              | 678                       | 0               | 678                 | 0             | 0       | 8                | 670                      |
| F6        | Redox Dark Surface           | 678                       | 0               | 678                 | 0             | 0       | 59               | 619                      |
| F7        | Depleted Dark Surface        | 678                       | 0               | 678                 | 0             | 0       | 59               | 619                      |
| F8        | Redox Depressions            | 678                       | 0               | 0                   | 678           | 0       | 0                | 678                      |
| F10       | Marl                         | 81                        | 0               | 0                   | 81            | 0       | 0                | 81                       |
| F11       | Depleted Ochric              | 0                         | 0               | 0                   | 0             | 0       | 0                | 0                        |
| F12       | Iron-Manganese Masses        | 154                       | 0               | 0                   | 154           | 0       | 0                | 154                      |
| F13       | Umbric Surface               | 132                       | 0               | 0                   | 132           | 0       | 0                | 132                      |
| F16       | High Plains Depressions      | 12                        | 0               | 0                   | 12            | 0       | 0                | 12                       |
| F17       | Delta Ochric                 | 0                         | 0               | 0                   | 0             | 0       | 0                | 0                        |
| F18       | Reduced Vertic               | 0                         | 0               | 0                   | 0             | 0       | 0                | 0                        |
| F19       | Piedmont Flood Plain Soils   | 21                        | 0               | 0                   | 21            | 0       | 0                | 21                       |
| F20       | Anomalous Bright Loamy Soils | 21                        | 0               | 0                   | 21            | 0       | 0                | 21                       |
| F21       | Red Parent Material          | 18                        | 0               | 0                   | 18            | 0       | 0                | 18                       |
| F22       | Very Shallow Dark Surface    | 22                        | 0               | 0                   | 22            | 0       | 0                | 22                       |

## Pedon-level evidence totals

- Pedons with at least one approved indicator present: 9
- Pedons with no indicator demonstrated among implemented/applicable rules: 768
- Pedons insufficient for every geographically applicable implemented rule: 10

`No indicator demonstrated` does not mean nonhydric. The non-executable approved indicators remain in the rulebook and data crosswalk but do not contribute positive or negative evidence.

## Implementation details

- Measurements using â€œsoil surfaceâ€ use NASIS absolute described depths.
- F6/F7 explicitly derive the mineral-soil datum from the first non-O horizon.
- Continuous candidate layers may span adjacent NASIS horizons; gaps break continuity.
- Only identifiable moist colors are used. Dry colors are never substituted.
- F3/A11/A12 require explicit depletion/reduction language plus the manual's color/redox conditions; low chroma alone never establishes a depleted matrix.
- A11/A12 sandy overburden remains insufficient where the required hand-lens masked-particle percentage is absent.
- Gley tests require an explicit qualifying gley-page hue and value, not a generic gray name.

## Reproducibility

Run `python scripts/kssl/implement_nrcs_v93_indicators.py` from the repository root with the staged official manual, errata, and MLRA v5.2 shapefile. Source Access data are never written.

## QA examples (fixed random seeds)

The following examples show the exact normalized NASIS horizon fields supplied to each rule. Nine apparent-positive cases are confirmed `INDICATOR_PRESENT`; the tenth is deliberately retained as an apparent-positive candidate with `INSUFFICIENT_INFORMATION`. Ten distinct not-demonstrated pedons follow. They must be reviewed before modeling.

### S2018PR153003 â€” A7 â€” INDICATOR_PRESENT

Requirements satisfied.

```text
designation  top  bottom  tex                                                                        nasis_matrix_color_raw nasis_color_moisture_status                                                                                                          nasis_redox_raw  redox_pct
          A  0.0     9.0 loam              dark brown (7.5YR 3/2) broken face, very dark gray (10YR 3/1) broken face, moist                       moist                                                                                                                      NaN        NaN
         Bk  9.0    28.0 loam very dark grayish brown (10YR 3/2) broken face, very dark brown (10YR 2/2) broken face, moist                       moist                                                                                                                      NaN        NaN
       Bkkm 28.0    35.0  NaN         light reddish brown (2.5YR 7/3) broken face, pale brown (10YR 6/3) broken face, moist                       moist medium reddish yellow (5YR 6/8) and 2 percent fine prominent reddish yellow (5YR 6/8) masses of oxidized iron throughout        2.0
```
### S2015ND093034 â€” F2 â€” INDICATOR_PRESENT

Requirements satisfied.

```text
designation  top  bottom  tex                                                nasis_matrix_color_raw nasis_color_moisture_status nasis_redox_raw  redox_pct
         Ap  0.0    20.0 loam very dark grayish brown (10YR 3/2), very dark brown (10YR 2/2), moist                       moist             NaN        NaN
        ABk 20.0    36.0 loam                            brown (10YR 5/3), 10Y 4/3 (10Y 4/3), moist                       moist             NaN        NaN
         Bk 36.0    70.0 loam                        pale brown (10YR 6/3), brown (10YR 5/3), moist                       moist             NaN        NaN
        BCk 70.0   100.0 loam light yellowish brown (2.5Y 6/4), light olive brown (2.5Y 5/4), moist                       moist             NaN        NaN
```
### S2018PR055006 â€” A7 â€” INDICATOR_PRESENT

Requirements satisfied.

```text
designation  top  bottom       tex                                                           nasis_matrix_color_raw nasis_color_moisture_status nasis_redox_raw  redox_pct
          A  0.0    11.0      loam dark brown (10YR 3/3) broken face, very dark brown (10YR 2/2) broken face, moist                       moist             NaN        NaN
         Bk 11.0    37.0 clay loam brown (10YR 4/3) broken face, dark yellowish brown (10YR 3/4) broken face, moist                       moist             NaN        NaN
      Bkkm1 37.0    62.0 silt loam      very pale brown (10YR 8/2) broken face, white (10YR 8/1) broken face, moist                       moist             NaN        NaN
      Bkkm2 62.0   100.0 silt loam      very pale brown (10YR 8/3) broken face, white (10YR 8/1) broken face, moist                       moist             NaN        NaN
```
### S2016FL107023 â€” A7 â€” INDICATOR_PRESENT

Requirements satisfied.

```text
designation  top  bottom  tex                                                                        nasis_matrix_color_raw nasis_color_moisture_status nasis_redox_raw  redox_pct
          A  0.0    25.0 None                                                              black (10YR 2/1) mucky fine sand                         NaN             NaN        NaN
        Bh1 25.0    40.0 None                                                           very dark gray (10YR 3/1) fine sand                         NaN             NaN        NaN
        Bh2 40.0   100.0 None 70 percent dark brown (7.5YR 3/3) and 30 percent very dark grayish brown (10YR 3/2) fine sand                         NaN             NaN        NaN
```
### S2018PR055012 â€” A7 â€” INDICATOR_PRESENT

Requirements satisfied.

```text
designation  top  bottom             tex                                                                   nasis_matrix_color_raw nasis_color_moisture_status nasis_redox_raw  redox_pct
          A  0.0    10.0      sandy loam       dark brown (7.5YR 3/2) broken face, very dark brown (7.5YR 2/2) broken face, moist                       moist             NaN        NaN
       Bkkm 10.0    31.0             NaN   light gray (2.5Y 7/2) broken face, light yellowish brown (2.5Y 6/3) broken face, moist                       moist             NaN        NaN
         Bk 31.0    44.0            loam dark brown (10YR 3/3) broken face, very dark grayish brown (10YR 3/2) broken face, moist                       moist             NaN        NaN
        Bkk 44.0   100.0 sandy clay loam   grayish brown (2.5Y 5/2) broken face, dark grayish brown (2.5Y 4/2) broken face, moist                       moist             NaN        NaN
```
### S2016FL107005 â€” A7 â€” INDICATOR_PRESENT

Requirements satisfied.

```text
designation  top  bottom  tex                     nasis_matrix_color_raw nasis_color_moisture_status nasis_redox_raw  redox_pct
         A1  0.0    20.0 None           black (10YR 2/1) mucky fine sand                         NaN             NaN        NaN
         A2 20.0    60.0 None        very dark gray (10YR 3/1) fine sand                         NaN             NaN        NaN
          C 60.0   100.0 None light yellowish brown (2.5Y 6/3) fine sand                         NaN             NaN        NaN
```
### S2018PR153015 â€” A7 â€” INDICATOR_PRESENT

Requirements satisfied.

```text
designation  top  bottom        tex                                                                      nasis_matrix_color_raw nasis_color_moisture_status nasis_redox_raw  redox_pct
         A1  0.0     6.0 sandy loam                                            , dark olive brown (2.5Y 3/3) broken face, moist                       moist             NaN        NaN
         A2  6.0    16.0  clay loam                      brown (10YR 4/3) broken face, dark brown (10YR 3/3) broken face, moist                       moist             NaN        NaN
        ABk 16.0    31.0  clay loam       dark yellowish brown (10YR 4/4) broken face, dark brown (10YR 3/3) broken face, moist                       moist             NaN        NaN
       Bkk1 31.0    40.0  clay loam            pale brown (10YR 6/3) broken face, yellowish brown (10YR 5/4) broken face, moist                       moist             NaN        NaN
       Bkk2 40.0    72.0  clay loam light yellowish brown (10YR 6/4) broken face, brownish yellow (10YR 6/6) broken face, moist                       moist             NaN        NaN
          C 72.0   100.0  clay loam    light yellowish brown (2.5Y 6/4) broken face, olive yellow (2.5Y 6/6) broken face, moist                       moist             NaN        NaN
```
### S2018PR153014 â€” A7 â€” INDICATOR_PRESENT

Requirements satisfied.

```text
designation  top  bottom       tex                                                      nasis_matrix_color_raw nasis_color_moisture_status nasis_redox_raw  redox_pct
          A  0.0     8.0 silt loam very dark brown (10YR 2/2) broken face, black (10YR 2/1) broken face, moist                       moist             NaN        NaN
         AC  8.0    30.0      loam      dark brown (10YR 3/3) broken face, black (10YR 2/1) broken face, moist                       moist             NaN        NaN
```
### S2018PR059017 â€” A7 â€” INDICATOR_PRESENT

Requirements satisfied.

```text
designation  top  bottom  tex                                                                                nasis_matrix_color_raw nasis_color_moisture_status nasis_redox_raw  redox_pct
          A  0.0    20.0 loam very dark grayish brown (10YR 3/2) broken face, very dark grayish brown (10YR 3/2) broken face, moist                       moist             NaN        NaN
```
### S2017VA043011 â€” S5 â€” INSUFFICIENT_INFORMATION

no continuous 10-cm sandy layer meets matrix and redox requirements; Missing: identifiable moist matrix color, redox percentage/type/contrast

```text
designation  top  bottom  tex                             nasis_matrix_color_raw nasis_color_moisture_status nasis_redox_raw  redox_pct
          A  0.0    13.0 clay     dark brown (7.5YR 3/3) very channery silt loam                         NaN             NaN        NaN
         BA 13.0    33.0 clay dark reddish brown (5YR 3/4) very cobbly silt loam                         NaN             NaN        NaN
        Bw1 33.0    80.0 clay          strong brown (7.5YR 4/6) very cobbly loam                         NaN             NaN        NaN
       2Bw2 80.0   100.0 clay                      strong brown (7.5YR 5/8) loam                         NaN             NaN        NaN
```
### S2017CA039010 â€” A1 â€” INDICATOR_NOT_DEMONSTRATED

taxonomy is not qualifying Histosol/Histel

```text
designation  top  bottom               tex                                                              nasis_matrix_color_raw nasis_color_moisture_status nasis_redox_raw  redox_pct
          A  0.0    22.0 coarse sandy loam grayish brown (10YR 5/2) crushed, very dark grayish brown (10YR 3/2) crushed, moist                       moist             NaN        NaN
        Bt1 22.0    58.0        sandy loam                 brown (7.5YR 5/3) broken face, brown (7.5YR 4/3) broken face, moist                       moist             NaN        NaN
        Bt2 58.0    64.0   sandy clay loam                 brown (7.5YR 5/4) broken face, brown (7.5YR 4/3) broken face, moist                       moist             NaN        NaN
```
### S2016WI099006 â€” A1 â€” INDICATOR_NOT_DEMONSTRATED

taxonomy is not qualifying Histosol/Histel

```text
designation  top  bottom  tex                            nasis_matrix_color_raw nasis_color_moisture_status                                                                    nasis_redox_raw  redox_pct
          A  0.0     4.0 None           very dark brown (7.5YR 2.5/2) fine sand                         NaN                                                                                NaN        NaN
        A/E  4.0    12.0 None                  dark brown (7.5YR 3/2) fine sand                         NaN                                                                                NaN        NaN
        Bhs 12.0    27.0 None     very dark brown (7.5YR 2.5/3) loamy fine sand                         NaN                                                                                NaN        NaN
        Bs1 27.0    48.0 None   dark brown (7.5YR 3/4) gravelly loamy fine sand                         NaN                                                                                NaN        NaN
        Bs2 48.0    57.0 None                   brown (7.5YR 4/4) gravelly sand                         NaN                                                                                NaN        NaN
       2BCd 57.0    75.0 None strong brown (7.5YR 4/6) very gravelly loamy sand                         NaN 20 percent medium distinct yellowish red (5YR 4/6), moist, masses of oxidized iron       20.0
       2Cd1 75.0    92.0 None        brown (7.5YR 4/3) very gravelly loamy sand                         NaN                                                                                NaN        NaN
       2Cd2 92.0   100.0 None             brown (7.5YR 4/3) gravelly loamy sand                         NaN 5 percent medium prominent yellowish red (5YR 4/6), moist, masses of oxidized iron        5.0
```
### S2015CO075007 â€” A1 â€” INDICATOR_NOT_DEMONSTRATED

taxonomy is not qualifying Histosol/Histel

```text
designation  top  bottom       tex                                                              nasis_matrix_color_raw nasis_color_moisture_status nasis_redox_raw  redox_pct
         Ap  0.0    18.0      loam brown (10YR 5/3) broken face, very dark grayish brown (10YR 3/2) broken face, moist                       moist             NaN        NaN
        Bt1 18.0    43.0 clay loam brown (10YR 4/3) broken face, very dark grayish brown (10YR 3/2) broken face, moist                       moist             NaN        NaN
        Bt2 43.0    61.0 clay loam                   brown (10YR 5/3) broken face, brown (10YR 4/3) broken face, moist                       moist             NaN        NaN
         Bk 61.0   100.0      loam              pale brown (10YR 6/3) broken face, brown (10YR 5/3) broken face, moist                       moist             NaN        NaN
```
### S2016MI053026 â€” A1 â€” INDICATOR_NOT_DEMONSTRATED

taxonomy is not qualifying Histosol/Histel

```text
designation   top  bottom  tex               nasis_matrix_color_raw nasis_color_moisture_status                                                                 nasis_redox_raw  redox_pct
         Oe   0.0     9.0 None moderately decomposed plant material                         NaN                                                                             NaN        NaN
          E   9.0    17.0 None                      fine sandy loam                         NaN                                                                             NaN        NaN
        Bs1  17.0    28.0 None                           sandy loam                         NaN                                                                             NaN        NaN
        Bs2  28.0    56.0 None                           sandy loam                         NaN                                                                             NaN        NaN
         E'  56.0   110.0 None                stony loamy fine sand                         NaN 2 percent fine distinct yellowish red (5YR 4/6), moist, masses of oxidized iron        2.0
        2Bt 110.0   151.0 None                           sandy loam                         NaN                                                                             NaN        NaN
```
### S2015KS087101 â€” A1 â€” INDICATOR_NOT_DEMONSTRATED

taxonomy is not qualifying Histosol/Histel

```text
designation  top  bottom  tex                              nasis_matrix_color_raw nasis_color_moisture_status                                                                                                                                                                                                                                                                   nasis_redox_raw  redox_pct
         A1  0.0    18.0 clay very dark brown (10YR 2/2) interior silty clay loam                         NaN                                                                                                                                                                                                                                                                               NaN        NaN
         A2 18.0    29.0 clay very dark brown (10YR 2/2) interior silty clay loam                         NaN                                                                                                                                                                                                                                                                               NaN        NaN
      Btss1 29.0    50.0 clay             very dark gray (10YR 3/1) interior clay                         NaN 1 percent medium distinct spherical strongly coherent cemented iron-manganese concretions with clear boundaries throughout and 15 percent fine prominent spherical noncoherent cemented strong brown (7.5YR 5/6), moist, masses of oxidized iron with clear boundaries throughout       15.0
      Btss2 50.0    67.0 clay         dark grayish brown (10YR 4/2) interior clay                         NaN         1 percent medium distinct spherical strongly coherent cemented iron-manganese concretions with clear boundaries throughout and 15 percent fine distinct spherical noncoherent cemented brown (7.5YR 5/4), moist, masses of oxidized iron with clear boundaries throughout       15.0
        Btk 67.0   100.0 clay                      brown (10YR 5/3) interior clay                         NaN                                                                                                                                                                                     25 percent medium prominent spherical noncoherent cemented masses of oxidized iron throughout       25.0
```
### S2015KS161103 â€” A1 â€” INDICATOR_NOT_DEMONSTRATED

taxonomy is not qualifying Histosol/Histel

```text
designation  top  bottom             tex                                               nasis_matrix_color_raw nasis_color_moisture_status nasis_redox_raw  redox_pct
         A1  0.0    12.0 silty clay loam very dark gray (10YR 3/1) interior, black (10YR 2/1) interior, moist                       moist             NaN        NaN
         A2 12.0    27.0 silty clay loam very dark gray (10YR 3/1) interior, black (10YR 2/1) interior, moist                       moist             NaN        NaN
```
### S2018AL023009 â€” A1 â€” INDICATOR_NOT_DEMONSTRATED

taxonomy is not qualifying Histosol/Histel

```text
designation  top  bottom  tex               nasis_matrix_color_raw nasis_color_moisture_status                                                                                                                                                                                                                                                                                                                                                                                                                                nasis_redox_raw  redox_pct
          A  0.0    17.0 None dark yellowish brown (10YR 4/4) loam                         NaN                                                                                                                                                               5 percent fine distinct irregular noncoherent cemented dark grayish brown (10YR 4/2), moist, iron depletions with clear boundaries in matrix and 5 percent fine distinct irregular noncoherent cemented brown (10YR 5/3), moist, iron depletions with clear boundaries in matrix        5.0
         Bw 17.0    31.0 None                brown (10YR 5/3) loam                         NaN 2 percent fine distinct spherical weakly coherent cemented black (10YR 2/1), moist, iron-manganese concretions with sharp boundaries in matrix and 5 percent fine distinct irregular noncoherent cemented grayish brown (10YR 5/2), moist, iron depletions with clear boundaries in matrix and 5 percent fine distinct irregular noncoherent cemented strong brown (7.5YR 4/6), moist, masses of oxidized iron with clear boundaries in matrix        5.0
        Bg1 31.0    59.0 None   grayish brown (10YR 5/2) clay loam                         NaN         5 percent fine distinct irregular noncoherent cemented brown (10YR 5/3), moist, iron depletions with clear boundaries in matrix and 5 percent fine distinct spherical weakly coherent cemented black (10YR 2/1), moist, iron-manganese concretions with sharp boundaries in matrix and 7 percent fine distinct irregular noncoherent cemented strong brown (7.5YR 5/6), moist, masses of oxidized iron with clear boundaries in matrix        7.0
        Bg2 59.0   100.0 None   grayish brown (10YR 5/2) clay loam                         NaN        5 percent fine distinct irregular noncoherent cemented brown (10YR 5/3), moist, iron depletions with clear boundaries in matrix and 5 percent fine distinct spherical weakly coherent cemented black (10YR 2/1), moist, iron-manganese concretions with sharp boundaries in matrix and 20 percent fine distinct irregular noncoherent cemented strong brown (7.5YR 5/6), moist, masses of oxidized iron with clear boundaries in matrix       20.0
```
### S2016TN001033 â€” A1 â€” INDICATOR_NOT_DEMONSTRATED

taxonomy is not qualifying Histosol/Histel

```text
designation  top  bottom  tex                                                    nasis_matrix_color_raw nasis_color_moisture_status nasis_redox_raw  redox_pct
          A  0.0     8.0 None                           brown (10YR 4/3) broken face very channery loam                         NaN             NaN        NaN
         Bw  8.0    20.0 None 88 percent dark yellowish brown (10YR 4/4) broken face very channery loam                         NaN             NaN        NaN
```
### S2018AK185123 â€” A1 â€” INDICATOR_NOT_DEMONSTRATED

taxonomy is not qualifying Histosol/Histel

```text
designation  top  bottom  tex                                                                                                nasis_matrix_color_raw nasis_color_moisture_status nasis_redox_raw  redox_pct
        E/A  1.0     9.0 clay 70 percent brown (7.5YR 4/3) broken face and 30 percent very dusky red (7.5R 2.5/3) broken face stony stony silt loam                         NaN             NaN        NaN
         Bw  9.0    27.0 clay                                                         brown (7.5YR 4/4) broken face extremely stony fine sandy loam                         NaN             NaN        NaN
         BC 27.0    60.0 clay                                           dark yellowish brown (10YR 4/4) broken face extremely stony fine sandy loam                         NaN             NaN        NaN
          C 60.0   105.0 clay                                                               brown (10YR 4/3) broken face extremely stony loamy sand                         NaN             NaN        NaN
```
### S2015KS161106 â€” A1 â€” INDICATOR_NOT_DEMONSTRATED

taxonomy is not qualifying Histosol/Histel

```text
designation  top  bottom             tex                                                                     nasis_matrix_color_raw nasis_color_moisture_status nasis_redox_raw  redox_pct
         A1  0.0    17.0 silty clay loam                      very dark brown (10YR 2/2) interior, black (10YR 2/1) interior, moist                       moist             NaN        NaN
         A2 17.0    40.0 silty clay loam dark grayish brown (10YR 4/2) interior, very dark grayish brown (10YR 3/2) interior, moist                       moist             NaN        NaN
        2Bw 40.0    60.0            clay dark grayish brown (10YR 4/2) interior, very dark grayish brown (10YR 3/2) interior, moist                       moist             NaN        NaN
        2Bk 60.0    80.0      silty clay                  light brownish gray (10YR 6/2) interior, brown (10YR 5/3) interior, moist                       moist             NaN        NaN
```

