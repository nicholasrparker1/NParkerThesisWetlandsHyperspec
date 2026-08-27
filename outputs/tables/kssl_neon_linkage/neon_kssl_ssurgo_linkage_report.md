# NEON–KSSL SSURGO component linkage report

## Scope

Official USDA NRCS Soil Data Access/SSURGO data only. `component.hydricrating` is preserved verbatim. No polygon-level rating, dominant-component shortcut, chemistry, MIR, spectral data, or `g` suffix was used. Ambiguous component matches remain unassigned.

## Spatial results

- Pedons: 777
- Successfully intersecting one SSURGO map unit: 771
- No SSURGO coverage: 0
- Ambiguous multiple spatial matches: 0
- Missing coordinates: 6

## Component-match and rating summary

| match_confidence | yes | no  | unranked | missing |
| ---------------- | --- | --- | -------- | ------- |
| AMBIGUOUS        | 0   | 0   | 0        | 219     |
| EXACT            | 23  | 292 | 0        | 2       |
| HIGH             | 0   | 4   | 0        | 0       |
| MEDIUM           | 12  | 28  | 0        | 1       |
| UNMATCHED        | 0   | 0   | 0        | 196     |

High confidence means `EXACT` or `HIGH` for site metrics:

- NEON sites with at least one high-confidence hydric=yes pedon: 10
- NEON sites with at least one high-confidence hydric=no pedon: 33
- NEON sites containing both: 9

## Field-indicator validation

| user_pedon_id | indicator_code | areasymbol | mukey   | musym | muname                                                                | selected_cokey | selected_compname | match_confidence | selected_hydricrating | agreement_disagreement |
| ------------- | -------------- | ---------- | ------- | ----- | --------------------------------------------------------------------- | -------------- | ----------------- | ---------------- | --------------------- | ---------------------- |
| S2015ND093034 | F2             | ND093      | 3312344 | C26A  | Tonka-Parnell complex, 0 to 1 percent slopes, Missouri Coteau         | nan            | nan               | AMBIGUOUS        | nan                   | UNRESOLVED             |
| S2016FL107005 | A7             | FL107      | 323416  | 5     | Placid fine sand, frequently ponded, 0 to 1 percent slopes            | 26572353       | Placid            | EXACT            | Yes                   | AGREEMENT              |
| S2016FL107023 | A7             | FL107      | 323391  | 27    | Samsula muck, frequently ponded, 0 to 1 percent slopes                | nan            | nan               | AMBIGUOUS        | nan                   | UNRESOLVED             |
| S2018PR055006 | A7             | PR787      | 1407028 | PsF   | Pitahaya-Limestone outcrop-Seboruco complex, 40 to 60 percent slopes  | 27626924       | La Covana         | EXACT            | No                    | DISAGREEMENT           |
| S2018PR055012 | A7             | PR787      | 1407028 | PsF   | Pitahaya-Limestone outcrop-Seboruco complex, 40 to 60 percent slopes  | 27626924       | La Covana         | EXACT            | No                    | DISAGREEMENT           |
| S2018PR059017 | A7             | PR688      | 326850  | TuF   | Tuque stony clay loam, 12 to 60 percent slopes                        | nan            | nan               | UNMATCHED        | nan                   | UNRESOLVED             |
| S2018PR153003 | A7             | PR787      | 1407028 | PsF   | Pitahaya-Limestone outcrop-Seboruco complex, 40 to 60 percent slopes  | 27626924       | La Covana         | EXACT            | No                    | DISAGREEMENT           |
| S2018PR153014 | A7             | PR787      | 1407028 | PsF   | Pitahaya-Limestone outcrop-Seboruco complex, 40 to 60 percent slopes  | 27626922       | Pitahaya          | EXACT            | No                    | DISAGREEMENT           |
| S2018PR153015 | A7             | PR787      | 1716023 | LcE   | La Covana-Limestone outcrop-Seboruco complex, 12 to 40 percent slopes | nan            | nan               | AMBIGUOUS        | nan                   | UNRESOLVED             |
Validation totals:

- Successfully component-matched: 5 of 9
- SSURGO hydricrating=Yes: 1
- SSURGO hydricrating=No: 4
- SSURGO hydricrating=unranked: 0
- Ambiguous or unmatched: 4

### Disagreement investigation

One Florida A7 pedon (`S2016FL107005`) agrees with its exact Placid component, rated `Yes`. Four Puerto Rico A7 pedons have exact normalized NASIS-to-component name matches but the matched La Covana or Pitahaya components are rated `No`. The A7 evidence is an explicitly described mucky modified mineral surface layer at the sampled point, whereas `component.hydricrating` is the official rating of the correlated SSURGO component. Both authoritative results are retained without reconciliation or relabeling. The other four indicator-positive pedons remain ambiguous or unmatched and therefore have no inherited component rating.

## QA audits

### S2015ND093026 — EXACT

Coordinate: 47.151072, -99.253018  
NASIS taxon: Parnell  
Map unit: ND093 / C24A / 3312341 — Parnell silty clay loam, 0 to 1 percent slopes, Missouri Coteau  
Selected: Parnell (27720308); hydricrating=Yes  
Reason: Unique exact normalized NASIS taxon/component-name match within the intersected map unit.

```text
compname    cokey comppct_r  taxorder                  taxsubgrp        localphase hydricrating  match_score  candidate_selected
 Parnell 27720308        64 Mollisols         Vertic Argiaquolls               NaN          Yes   195.000000                True
 Vallers 27720307        10 Mollisols         Typic Calciaquolls               NaN          Yes    35.000000               False
   Tonka 27720309        10 Mollisols      Argiaquic Argialbolls               NaN          Yes     5.833333               False
 Southam 27720310        10 Mollisols Cumulic Vertic Endoaquolls               NaN          Yes    25.000000               False
 Hamerly 27720312         3 Mollisols         Aeric Calciaquolls               NaN           No    35.000000               False
 Vallers 27720306         2 Mollisols         Typic Calciaquolls moderately saline          Yes    35.000000               False
    Heil 27720311         1 Vertisols          Typic Natraquerts               NaN          Yes    -7.272727               False
```
### S2015ND093028 — EXACT

Coordinate: 47.140568, -99.252037  
NASIS taxon: Parnell  
Map unit: ND093 / C26A / 3312344 — Tonka-Parnell complex, 0 to 1 percent slopes, Missouri Coteau  
Selected: Parnell (27720298); hydricrating=Yes  
Reason: Unique exact normalized NASIS taxon/component-name match within the intersected map unit.

```text
compname    cokey comppct_r  taxorder             taxsubgrp        localphase hydricrating  match_score  candidate_selected
   Tonka 27720297        60 Mollisols Argiaquic Argialbolls               NaN          Yes     5.833333               False
 Parnell 27720298        22 Mollisols    Vertic Argiaquolls               NaN          Yes   195.000000                True
 Vallers 27720295         5 Mollisols    Typic Calciaquolls moderately saline          Yes    35.000000               False
 Vallers 27720296         5 Mollisols    Typic Calciaquolls               NaN          Yes    35.000000               False
   Wyard 27720299         5 Mollisols     Typic Endoaquolls               NaN           No    31.666667               False
Bowbells 27720300         3 Mollisols    Pachic Argiustolls               NaN           No    14.000000               False
```
### S2015ND093030 — EXACT

Coordinate: 47.137925, -99.243418  
NASIS taxon: SND  
Map unit: ND093 / C24A / 3312341 — Parnell silty clay loam, 0 to 1 percent slopes, Missouri Coteau  
Selected: Southam (27720310); hydricrating=Yes  
Reason: Unique exact normalized NASIS taxon/component-name match within the intersected map unit.

```text
compname    cokey comppct_r  taxorder                  taxsubgrp        localphase hydricrating  match_score  candidate_selected
 Parnell 27720308        64 Mollisols         Vertic Argiaquolls               NaN          Yes    27.000000               False
 Vallers 27720307        10 Mollisols         Typic Calciaquolls               NaN          Yes    27.000000               False
   Tonka 27720309        10 Mollisols      Argiaquic Argialbolls               NaN          Yes    11.666667               False
 Southam 27720310        10 Mollisols Cumulic Vertic Endoaquolls               NaN          Yes   195.000000                True
 Hamerly 27720312         3 Mollisols         Aeric Calciaquolls               NaN           No    35.000000               False
 Vallers 27720306         2 Mollisols         Typic Calciaquolls moderately saline          Yes    27.000000               False
    Heil 27720311         1 Vertisols          Typic Natraquerts               NaN          Yes   -13.636364               False
```
### S2015ND093031 — EXACT

Coordinate: 47.128, -99.243  
NASIS taxon: Tonka  
Map unit: ND093 / C819B / 2566841 — Lehr-Wabek loams, 2 to 6 percent slopes  
Selected: Tonka (27719362); hydricrating=Yes  
Reason: Unique exact normalized NASIS taxon/component-name match within the intersected map unit.

```text
compname    cokey comppct_r  taxorder             taxsubgrp localphase hydricrating  match_score  candidate_selected
    Lehr 27719367        47 Mollisols     Typic Haplustolls        NaN           No     0.000000               False
   Wabek 27719366        35 Mollisols     Entic Haplustolls        NaN           No   -13.000000               False
  Bowdle 27719364        10 Mollisols    Pachic Haplustolls        NaN           No     6.363636               False
   Appam 27719363         5 Mollisols     Typic Haplustolls        NaN           No   -13.000000               False
   Tonka 27719362         1 Mollisols Argiaquic Argialbolls        NaN          Yes   195.000000                True
Parshall 27719365         1 Mollisols    Pachic Haplustolls        NaN           No   -14.615385               False
  Divide 27719368         1 Mollisols    Aeric Calciaquolls        NaN           No     0.000000               False
```
### S2015AL063012 — EXACT

Coordinate: 32.5420722, -87.8072  
NASIS taxon: Leaf  
Map unit: AL063 / LF / 329668 — Leaf-Angie association  
Selected: Leaf (27276264); hydricrating=Yes  
Reason: Unique exact normalized NASIS taxon/component-name match within the intersected map unit.

```text
compname    cokey comppct_r taxorder        taxsubgrp localphase hydricrating  match_score  candidate_selected
    Leaf 27276264        41 Ultisols Typic Albaquults        NaN          Yes   175.000000                True
   Angie 27276263        39 Ultisols Aquic Hapludults        NaN           No   -12.222222               False
```
### S2016MI053032 — EXACT

Coordinate: 46.23211, -89.53488  
NASIS taxon: Cathro  
Map unit: MI053 / 41 / 1455943 — Lupton-Pleine-Cathro complex, 0 to 1 percent slopes  
Selected: Cathro (27105373); hydricrating=Yes  
Reason: Unique exact normalized NASIS taxon/component-name match within the intersected map unit.

```text
compname    cokey comppct_r    taxorder            taxsubgrp localphase hydricrating  match_score  candidate_selected
  Lupton 27105372        60   Histosols  Typic Haplosaprists        NaN          Yes    31.666667               False
  Pleine 27105371        23 Inceptisols    Histic Humaquepts        NaN          Yes   -20.000000               False
  Cathro 27105373        15   Histosols Terric Haplosaprists        NaN          Yes   195.000000                True
     Gay 27105370         2 Inceptisols    Aeric Endoaquepts        NaN          Yes   -12.222222               False
```
### S2016WI069053 — EXACT

Coordinate: 45.50556, -89.58755  
NASIS taxon: Capitola  
Map unit: WI069 / 3298B / 431633 — Moodig sandy loam, 0 to 4 percent slopes  
Selected: Capitola (27558096); hydricrating=Yes  
Reason: Unique exact normalized NASIS taxon/component-name match within the intersected map unit.

```text
compname    cokey comppct_r  taxorder                  taxsubgrp localphase hydricrating  match_score  candidate_selected
  Moodig 27558099        90 Spodosols            Alfic Epiaquods        NaN           No        -15.0               False
Capitola 27558096         5  Alfisols           Aeric Epiaqualfs        NaN          Yes        195.0                True
  Hatley 27558097         3  Alfisols          Aquic Glossudalfs        NaN           No         15.0               False
  Sarwet 27558098         2 Spodosols Alfic Oxyaquic Haplorthods        NaN           No        -10.0               False
```
### S2016WI099022 — EXACT

Coordinate: 45.804369, -90.0523  
NASIS taxon: Cathro  
Map unit: WI099 / 3045A / 627370 — Lupton, Cathro, and Tawas soils, 0 to 1 percent slopes  
Selected: Cathro (27592772); hydricrating=Yes  
Reason: Unique exact normalized NASIS taxon/component-name match within the intersected map unit.

```text
   compname    cokey comppct_r  taxorder            taxsubgrp localphase hydricrating  match_score  candidate_selected
     Lupton 27592773        40 Histosols  Typic Haplosaprists        NaN          Yes   -28.333333               False
     Cathro 27592772        30 Histosols Terric Haplosaprists        NaN          Yes   115.000000                True
      Tawas 27592774        25 Histosols Terric Haplosaprists        NaN          Yes   -33.636364               False
Seelyeville 27592771         5       NaN                  NaN        NaN          Yes     0.000000               False
```
### S2016WI069009 — EXACT

Coordinate: 45.48573, -89.56965  
NASIS taxon: Loxley  
Map unit: WI069 / 3008A / 431626 — Lupton and Cathro soils, 0 to 1 percent slopes  
Selected: Loxley (27558187); hydricrating=Yes  
Reason: Unique exact normalized NASIS taxon/component-name match within the intersected map unit.

```text
compname    cokey comppct_r  taxorder            taxsubgrp localphase hydricrating  match_score  candidate_selected
  Lupton 27558190        45 Histosols  Typic Haplosaprists        NaN          Yes    59.666667               False
  Cathro 27558189        35 Histosols Terric Haplosaprists        NaN          Yes    33.833333               False
Capitola 27558185         5  Alfisols     Aeric Epiaqualfs        NaN          Yes   -22.000000               False
 Beseman 27558186         5 Histosols Terric Haplosaprists        NaN          Yes    33.384615               False
  Loxley 27558187         5 Histosols  Typic Haplosaprists        NaN          Yes   183.000000                True
  Markey 27558188         5 Histosols Terric Haplosaprists        NaN          Yes    39.666667               False
```
### S2016WI069011 — EXACT

Coordinate: 45.497054, -89.554761  
NASIS taxon: Cathro  
Map unit: WI069 / 3008A / 431626 — Lupton and Cathro soils, 0 to 1 percent slopes  
Selected: Cathro (27558189); hydricrating=Yes  
Reason: Unique exact normalized NASIS taxon/component-name match within the intersected map unit.

```text
compname    cokey comppct_r  taxorder            taxsubgrp localphase hydricrating  match_score  candidate_selected
  Lupton 27558190        45 Histosols  Typic Haplosaprists        NaN          Yes    31.666667               False
  Cathro 27558189        35 Histosols Terric Haplosaprists        NaN          Yes   195.000000                True
Capitola 27558185         5  Alfisols     Aeric Epiaqualfs        NaN          Yes     0.000000               False
 Beseman 27558186         5 Histosols Terric Haplosaprists        NaN          Yes    65.384615               False
  Loxley 27558187         5 Histosols  Typic Haplosaprists        NaN          Yes    25.833333               False
  Markey 27558188         5 Histosols Terric Haplosaprists        NaN          Yes    51.666667               False
```
### S2012CO123001 — EXACT

Coordinate: 40.8131111, -104.7443889  
NASIS taxon: Ascalon  
Map unit: CO617 / 4 / 95132 — Ascalon fine sandy loam, 0 to 6 percent slopes  
Selected: Ascalon (26599030); hydricrating=No  
Reason: Unique exact normalized NASIS taxon/component-name match within the intersected map unit.

```text
compname    cokey comppct_r  taxorder          taxsubgrp localphase hydricrating  match_score  candidate_selected
 Ascalon 26599030        85 Mollisols Aridic Argiustolls        NaN           No   195.000000                True
  Olnest 26599031         8  Alfisols Aridic Haplustalfs        NaN           No    -9.230769               False
   Otero 26599029         7  Entisols Aridic Ustorthents        NaN           No   -34.166667               False
```
### S2013AL063001 — EXACT

Coordinate: 32.541, -87.8031667  
NASIS taxon: Angie  
Map unit: AL063 / LF / 329668 — Leaf-Angie association  
Selected: Angie (27276263); hydricrating=No  
Reason: Unique exact normalized NASIS taxon/component-name match within the intersected map unit.

```text
compname    cokey comppct_r taxorder        taxsubgrp localphase hydricrating  match_score  candidate_selected
    Leaf 27276264        41 Ultisols Typic Albaquults        NaN          Yes   -12.222222               False
   Angie 27276263        39 Ultisols Aquic Hapludults        NaN           No   135.000000                True
```
### S2013VA187001 — EXACT

Coordinate: 38.89209, -78.13764  
NASIS taxon: Lew  
Map unit: VA187 / 22E / 518823 — Lew loam, 25 to 65 percent slopes, very stony  
Selected: Lew (27340363); hydricrating=No  
Reason: Unique exact normalized NASIS taxon/component-name match within the intersected map unit.

```text
compname    cokey comppct_r taxorder        taxsubgrp localphase hydricrating  match_score  candidate_selected
     Lew 27340363        90 Alfisols Ultic Hapludalfs        NaN           No        195.0                True
```
### S2013MI053001 — EXACT

Coordinate: 46.2362222, -89.5391389  
NASIS taxon: Tula  
Map unit: MI053 / 5172C / 1455968 — Gogebic, sandy substratum-Pence-Cathro complex, 0 to 18 percent slopes  
Selected: Tula (27105213); hydricrating=No  
Reason: Unique exact normalized NASIS taxon/component-name match within the intersected map unit.

```text
compname    cokey comppct_r  taxorder                   taxsubgrp       localphase hydricrating  match_score  candidate_selected
 Gogebic 27105215        60 Spodosols Alfic Oxyaquic Fragiorthods sandy substratum           No     0.000000               False
  Cathro 27105216        15 Histosols        Terric Haplosaprists              NaN          Yes   -13.000000               False
   Pence 27105217        15 Spodosols           Typic Haplorthods sandy substratum           No   -20.000000               False
    Tula 27105213         5 Spodosols           Argic Fragiaquods              NaN           No   195.000000                True
Annalake 27105214         5 Spodosols  Alfic Oxyaquic Haplorthods              NaN           No    11.666667               False
```
### S2013TN001001 — EXACT

Coordinate: 35.964583, -84.282806  
NASIS taxon: Fullerton  
Map unit: TN001 / FoC / 1887391 — Fullerton-Pailo complex, 5 to 12 percent slopes  
Selected: Fullerton (26465199); hydricrating=No  
Reason: Unique exact normalized NASIS taxon/component-name match within the intersected map unit.

```text
 compname    cokey comppct_r taxorder        taxsubgrp localphase hydricrating  match_score  candidate_selected
Fullerton 26465199        65 Ultisols Typic Paleudults        NaN           No       195.00                True
    Pailo 26465197        26 Ultisols Typic Paleudults        NaN           No        50.00               False
  Minvale 26465198         9 Ultisols Typic Paleudults        NaN           No        68.75               False
```
### S2014AL007001 — EXACT

Coordinate: 32.9510611, -87.3941  
NASIS taxon: Smithdale  
Map unit: AL007 / MsF / 2232549 — Maubila-Smithdale complex, 15 to 35 percent slopes  
Selected: Smithdale (26916503); hydricrating=No  
Reason: Unique exact normalized NASIS taxon/component-name match within the intersected map unit.

```text
 compname    cokey comppct_r taxorder         taxsubgrp localphase hydricrating  match_score  candidate_selected
  Maubila 26916502        50 Ultisols  Aquic Hapludults        NaN           No    53.125000               False
Smithdale 26916503        35 Ultisols  Typic Hapludults        NaN           No   195.000000                True
     Bibb 26916501         5 Entisols Typic Fluvaquents        NaN          Yes   -34.615385               False
```
### S2014PR079001 — EXACT

Coordinate: 18.0218444, -67.0760833  
NASIS taxon: Cartagena  
Map unit: PR787 / CeA / 1379800 — Cartagena clay, 0 to 2 percent slopes  
Selected: Cartagena (27627145); hydricrating=No  
Reason: Unique exact normalized NASIS taxon/component-name match within the intersected map unit.

```text
   compname    cokey comppct_r  taxorder          taxsubgrp           localphase hydricrating  match_score  candidate_selected
  Cartagena 27627145        80 Vertisols  Sodic Haplusterts                  NaN           No   195.000000                True
         Fe 27627142         5 Vertisols  Sodic Haplusterts                  NaN           No    66.363636               False
    Aguirre 27627143         5 Vertisols   Sodic Epiaquerts  occasionally ponded          Yes    13.125000               False
    Guanica 27627144         5 Vertisols Typic Calciaquerts  occasionally ponded          Yes     8.750000               False
Fraternidad 27627141         2 Vertisols  Typic Haplusterts                  NaN           No    57.500000               False
 Urban land 27627138         1       NaN                NaN                  NaN           No    14.736842               False
      Vayas 27627139         1 Mollisols Vertic Endoaquolls occasionally flooded          Yes   -10.000000               False
    Poncena 27627140         1 Vertisols Typic Calciusterts                  NaN           No    37.500000               False
```
### S2014UT045001 — EXACT

Coordinate: 40.1783389, -112.4538139  
NASIS taxon: Taylorsflat  
Map unit: UT611 / 64 / 482173 — Taylorsflat loam, 1 to 5 percent slopes  
Selected: Taylorsflat (26351902); hydricrating=No  
Reason: Unique exact normalized NASIS taxon/component-name match within the intersected map unit.

```text
   compname    cokey comppct_r  taxorder            taxsubgrp localphase hydricrating  match_score  candidate_selected
Taylorsflat 26351902        90 Aridisols   Xeric Haplocalcids        NaN           No   195.000000                True
  Hiko Peak 26351904         4 Aridisols   Xeric Haplocalcids        NaN          NaN    47.000000               False
     Spager 26351903         3 Aridisols  Calcic Petrocalcids        NaN          NaN     8.235294               False
     Birdow 26351905         3 Mollisols Cumulic Haploxerolls        NaN          NaN   -15.882353               False
```
### S2014KS161501 — EXACT

Coordinate: 39.10354, -96.56356  
NASIS taxon: Florence  
Map unit: KS161 / 4530 / 1472305 — Benfield-Florence complex, 5 to 30 percent slopes  
Selected: Florence (26334567); hydricrating=No  
Reason: Unique exact normalized NASIS taxon/component-name match within the intersected map unit.

```text
compname    cokey comppct_r  taxorder                  taxsubgrp          localphase hydricrating  match_score  candidate_selected
Benfield 26334566        45 Mollisols        Udertic Argiustolls                 NaN           No    33.125000               False
Florence 26334567        30 Mollisols           Udic Argiustolls                 NaN           No   195.000000                True
   Clime 26334568         5 Mollisols    Udorthentic Haplustolls                 NaN           No    10.769231               False
 Labette 26334570         5 Mollisols           Udic Argiustolls                 NaN           No    54.000000               False
    Sogn 26334572         5 Mollisols         Lithic Haplustolls                 NaN           No    31.666667               False
   Tully 26334571         4 Mollisols         Pachic Argiustolls                 NaN           No    25.384615               False
   Konza 26334569         3 Mollisols        Udertic Paleustolls                 NaN           No    10.769231               False
  Pawnee 26334573         2 Mollisols Oxyaquic Vertic Argiudolls                 NaN           No   -10.000000               False
 Aquolls 26334574         1 Mollisols                        NaN occasionally ponded          Yes     0.666667               False
```
### S2014KS045001 — EXACT

Coordinate: 39.04175, -95.2043889  
NASIS taxon: Rosendale  
Map unit: KS045 / 7550 / 2421220 — Rosendale-Bendena silty clay loams, 3 to 40 percent slopes  
Selected: Rosendale (26317595); hydricrating=No  
Reason: Unique exact normalized NASIS taxon/component-name match within the intersected map unit.

```text
    compname    cokey comppct_r    taxorder           taxsubgrp localphase hydricrating  match_score  candidate_selected
   Rosendale 26317595        55 Inceptisols    Typic Eutrudepts        NaN           No   115.000000                True
     Bendena 26317598        27   Mollisols   Lithic Hapludolls        NaN           No    17.500000               False
      Martin 26317596        10   Mollisols Aquertic Argiudolls        NaN           No    44.666667               False
     Wallula 26317597         5   Mollisols    Typic Hapludolls        NaN           No    28.750000               False
Rock outcrop 26317599         3         NaN                 NaN        NaN           No     6.666667               False
```
### S2015ND093034 — AMBIGUOUS

Coordinate: 47.127281, -99.246569  
NASIS taxon: Zahl  
Map unit: ND093 / C26A / 3312344 — Tonka-Parnell complex, 0 to 1 percent slopes, Missouri Coteau  
Selected: nan (nan); hydricrating=nan  
Reason: Multiple plausible candidates remain without a decisive name/taxonomy margin.

```text
compname    cokey comppct_r  taxorder             taxsubgrp        localphase hydricrating  match_score  candidate_selected
   Tonka 27720297        60 Mollisols Argiaquic Argialbolls               NaN          Yes     7.777778               False
 Parnell 27720298        22 Mollisols    Vertic Argiaquolls               NaN          Yes    12.727273               False
 Vallers 27720295         5 Mollisols    Typic Calciaquolls moderately saline          Yes    12.727273               False
 Vallers 27720296         5 Mollisols    Typic Calciaquolls               NaN          Yes    12.727273               False
   Wyard 27720299         5 Mollisols     Typic Endoaquolls               NaN           No     7.777778               False
Bowbells 27720300         3 Mollisols    Pachic Argiustolls               NaN           No    25.833333               False
```
### S2016FL107005 — EXACT

Coordinate: 29.7225, -81.9858333333  
NASIS taxon: Placid  
Map unit: FL107 / 5 / 323416 — Placid fine sand, frequently ponded, 0 to 1 percent slopes  
Selected: Placid (26572353); hydricrating=Yes  
Reason: Unique exact normalized NASIS taxon/component-name match within the intersected map unit.

```text
compname    cokey comppct_r    taxorder            taxsubgrp localphase hydricrating  match_score  candidate_selected
  Placid 26572353        80 Inceptisols     Typic Humaquepts        NaN          Yes   195.000000                True
Basinger 26572356         7    Entisols  Spodic Psammaquents        NaN          Yes   -30.000000               False
  Myakka 26572354         5   Spodosols       Aeric Alaquods        NaN           No   -14.166667               False
  Gentry 26572351         3   Mollisols   Arenic Argiaquolls        NaN          Yes   -40.000000               False
 Samsula 26572352         3   Histosols Terric Haplosaprists        NaN          Yes    -9.230769               False
   Felda 26572355         2    Alfisols   Arenic Endoaqualfs        NaN          Yes   -27.272727               False
```
### S2016FL107023 — AMBIGUOUS

Coordinate: 29.7225333335, -81.9856444443  
NASIS taxon: Ona  
Map unit: FL107 / 27 / 323391 — Samsula muck, frequently ponded, 0 to 1 percent slopes  
Selected: nan (nan); hydricrating=nan  
Reason: Multiple plausible candidates remain without a decisive name/taxonomy margin.

```text
 compname    cokey comppct_r    taxorder            taxsubgrp localphase hydricrating  match_score  candidate_selected
  Samsula 26572233        85   Histosols Terric Haplosaprists        NaN          Yes   -13.000000               False
   Myakka 26572234         3   Spodosols       Aeric Alaquods        NaN          Yes    47.777778               False
   Kaliga 26572238         3   Histosols Terric Haplosaprists        NaN          Yes   -32.222222               False
 Basinger 26572239         3    Entisols  Spodic Psammaquents        NaN          Yes   -33.636364               False
  Anclote 26572235         2   Mollisols    Typic Endoaquolls        NaN          Yes   -13.000000               False
Floridana 26572236         2   Mollisols   Arenic Argiaquolls        NaN          Yes   -22.500000               False
  Sanibel 26572237         2 Inceptisols    Histic Humaquepts        NaN          Yes   -13.000000               False
```
### S2018PR153003 — EXACT

Coordinate: 17.973025, -66.861828  
NASIS taxon: La Covana  
Map unit: PR787 / PsF / 1407028 — Pitahaya-Limestone outcrop-Seboruco complex, 40 to 60 percent slopes  
Selected: La Covana (27626924); hydricrating=No  
Reason: Unique exact normalized NASIS taxon/component-name match within the intersected map unit.

```text
         compname    cokey comppct_r  taxorder                  taxsubgrp                  localphase hydricrating  match_score  candidate_selected
         Pitahaya 27626922        60  Entisols        Typic Torriorthents                         NaN           No    -7.647059               False
Limestone outcrop 27626921        20       NaN                        NaN Aridic Soil Moisture Regime           No     0.076923               False
         Seboruco 27626923        15 Aridisols          Typic Calciargids                         NaN           No   -11.764706               False
        La Covana 27626924         5 Aridisols Calcic Lithic Petrocalcids                         NaN           No   195.000000                True
```
### S2018PR055006 — EXACT

Coordinate: 17.963656, -66.87581  
NASIS taxon: La Covana  
Map unit: PR787 / PsF / 1407028 — Pitahaya-Limestone outcrop-Seboruco complex, 40 to 60 percent slopes  
Selected: La Covana (27626924); hydricrating=No  
Reason: Unique exact normalized NASIS taxon/component-name match within the intersected map unit.

```text
         compname    cokey comppct_r  taxorder                  taxsubgrp                  localphase hydricrating  match_score  candidate_selected
         Pitahaya 27626922        60  Entisols        Typic Torriorthents                         NaN           No    -7.647059               False
Limestone outcrop 27626921        20       NaN                        NaN Aridic Soil Moisture Regime           No     0.076923               False
         Seboruco 27626923        15 Aridisols          Typic Calciargids                         NaN           No   -11.764706               False
        La Covana 27626924         5 Aridisols Calcic Lithic Petrocalcids                         NaN           No   195.000000                True
```
### S2018PR055012 — EXACT

Coordinate: 17.95146, -66.89913  
NASIS taxon: La Covana  
Map unit: PR787 / PsF / 1407028 — Pitahaya-Limestone outcrop-Seboruco complex, 40 to 60 percent slopes  
Selected: La Covana (27626924); hydricrating=No  
Reason: Unique exact normalized NASIS taxon/component-name match within the intersected map unit.

```text
         compname    cokey comppct_r  taxorder                  taxsubgrp                  localphase hydricrating  match_score  candidate_selected
         Pitahaya 27626922        60  Entisols        Typic Torriorthents                         NaN           No    -7.647059               False
Limestone outcrop 27626921        20       NaN                        NaN Aridic Soil Moisture Regime           No     0.076923               False
         Seboruco 27626923        15 Aridisols          Typic Calciargids                         NaN           No   -11.764706               False
        La Covana 27626924         5 Aridisols Calcic Lithic Petrocalcids                         NaN           No   195.000000                True
```
### S2018PR153014 — EXACT

Coordinate: 17.95561, -66.85236  
NASIS taxon: Pitahaya  
Map unit: PR787 / PsF / 1407028 — Pitahaya-Limestone outcrop-Seboruco complex, 40 to 60 percent slopes  
Selected: Pitahaya (27626922); hydricrating=No  
Reason: Unique exact normalized NASIS taxon/component-name match within the intersected map unit.

```text
         compname    cokey comppct_r  taxorder                  taxsubgrp                  localphase hydricrating  match_score  candidate_selected
         Pitahaya 27626922        60  Entisols        Typic Torriorthents                         NaN           No   195.000000                True
Limestone outcrop 27626921        20       NaN                        NaN Aridic Soil Moisture Regime           No    -2.400000               False
         Seboruco 27626923        15 Aridisols          Typic Calciargids                         NaN           No   -40.000000               False
        La Covana 27626924         5 Aridisols Calcic Lithic Petrocalcids                         NaN           No    -7.647059               False
```
### S2018PR153015 — AMBIGUOUS

Coordinate: 17.97677, -66.86211  
NASIS taxon: Altamira  
Map unit: PR787 / LcE / 1716023 — La Covana-Limestone outcrop-Seboruco complex, 12 to 40 percent slopes  
Selected: nan (nan); hydricrating=nan  
Reason: Multiple plausible candidates remain without a decisive name/taxonomy margin.

```text
         compname    cokey comppct_r  taxorder                  taxsubgrp                  localphase hydricrating  match_score  candidate_selected
        La Covana 27626967        60 Aridisols Calcic Lithic Petrocalcids                         NaN           No    12.352941               False
Limestone outcrop 27626968        20       NaN                        NaN Aridic Soil Moisture Regime           No     0.400000               False
         Seboruco 27626969        15 Aridisols          Typic Calciargids                         NaN           No   -15.625000               False
         Pitahaya 27626970         5  Entisols        Typic Torriorthents                         NaN           No   -26.875000               False
```
### S2018PR059017 — UNMATCHED

Coordinate: 17.965356, -66.835344  
NASIS taxon: Pitahaya  
Map unit: PR688 / TuF / 326850 — Tuque stony clay loam, 12 to 60 percent slopes  
Selected: nan (nan); hydricrating=nan  
Reason: No candidate has adequate name or taxonomic agreement.

```text
compname    cokey comppct_r  taxorder                       taxsubgrp localphase hydricrating  match_score  candidate_selected
   Tuque 27626052       100 Mollisols Lithic Petrocalcic Calciustolls        NaN           No   -14.615385               False
```

