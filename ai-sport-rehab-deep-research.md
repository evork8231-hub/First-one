# AI × Sport × Taastusravi — kriitiline turu- ja võimalusanalüüs

**Kuupäev:** 8. september 2026
**Autor:** deep research analüüs (AI/ML analüütik + sporditehnoloogia + füsioteraapia tehnoloogia + healthtech investor + B2B SaaS strateegia vaatenurgast)
**Metoodika:** ~35 sihitud otsingut peer-reviewed kirjandusest (PubMed/PMC, Lancet, JOSPT, BJSM-tüüpi allikad), EL regulatsiooniallikatest, börsiettevõtete aruannetest, startup-andmebaasidest (Crunchbase/PitchBook/Tracxn) ja tööstuse allikatest. Iga oluline väide on märgistatud.

**Märgistus, mida kasutan läbivalt:**
- `[F]` = **fakt** sõltumatust allikast (teadusartikkel, börsiaruanne, regulaator)
- `[V]` = **vendor/tööstuse väide** (ettevõtte enda materjal, blogi, PR) — ei ole tõend
- `[H]` = **minu hinnang** olemasoleva info põhjal
- `[S]` = **spekulatsioon** — puudub piisav info

---

# 1. Executive Summary

**Lühivastus: valdkond on atraktiivne, aga MITTE seal, kus enamik inimesi arvab.**

Kolm asja, mis selle analüüsi tulemusena kõige tugevamalt välja tulid:

### 1.1. Kõige populaarsemad ideed on teaduslikult kõige nõrgemal pinnal

Neli "ilmselget" AI × sport ideed — **vigastusriski ennustamine**, **movement screening**, **return-to-play readiness score** ja **wearable recovery score** — on täpselt need, mida teadus kõige halvemini toetab:

- Acute:Chronic Workload Ratio (ACWR), kogu koormuspõhise vigastusennustuse aluspõhi, on matemaatiliselt vigane (acute load sisaldub chronic load'i arvutuses → kunstlik korrelatsioon r ≈ 0,5) ja süstemaatilised ülevaated soovitavad raamistiku kõrvale heita `[F]`
- Functional Movement Screen: hea korduvusega, aga **vigastuste ennustajana kehv** — meta-analüüsid tuvastavad tõsised sisemise ja välise valiidsuse probleemid `[F]`
- ML-põhised vigastusennustusmudelid annavad AUC 0,52–0,87, on treenitud kitsastel populatsioonidel (peamiselt eliidi meessportlased, jalgpall/korvpall/käsipall) ja **ei ole süstemaatiliselt paremad kui tavaline logistiline regressioon** `[F]`
- Kõige olulisem üksikleid: **return-to-sport kriteeriumide läbimine EI ole seotud madalama korduvvigastuse riskiga**. Uuringus, mis seda otse testis, oli teine ACL-vigastus kriteeriumid läbinutel 28,6% ja kriteeriumides läbi kukkunutel 19,7% `[F]`

See tähendab, et **"AI ennustab vigastusi" on toote lubadusena ohtlik** — mitte sellepärast, et AI oleks halb, vaid sellepärast, et signaal andmetes on nõrk ja tulemus pole valideeritav.

### 1.2. Kõige tugevamad tõendid on täiesti igavate asjade kohta

Mis on **tegelikult tõestatud**:
- **Telerehabilitatsioon on kliiniliselt mitte-halvem kui kohapealne füsioteraapia** kroonilise põlvevalu puhul (PEAK non-inferiority RCT, Lancet) ja degeneratiivse meniskirebendi puhul `[F]`
- **Harjutuspõhised vigastuste ennetusprogrammid vähendavad vigastusi ~40–50%**, aga nende **rakendamine on nii amatöör- kui profispordis üllatavalt madal** `[F]`
- Markerless pose estimation annab alajäseme liigesnurkadele MAE **alla 5°**, mis on kliiniliselt aktsepteeritavas vahemikus ja marker-põhiste süsteemide enda mõõtmisvea suurusjärgus `[F]`
- Dokumentatsioonikoormus, ravist väljalangevus ja adherentsuse puudumine on **mõõdetavad, kallid ja korduvad** probleemid `[F]`

Muster on selge: **AI ei suuda usaldusväärselt ennustada, kes vigastub, aga suudab odavalt koguda, struktureerida ja liigutada infot, mis täna maksab spetsialisti aega.** Raha on teises kohas kui glamuur.

### 1.3. Sport × rehab ristumiskoht on intellektuaalselt kõige huvitavam ja kommertsiaalselt kõige nõrgem

Vastus küsimusele 7 on **ei, mitte otseselt**. Sport toob kaasa brändi, huvitava probleemi ja tehnilise usaldusväärsuse — aga spordipoolel on väga vähe ostjaid, kellel on korduv eelarve. Meditsiinipoolel on korduv raha. Parim strateegia on **kasutada sporti sisenemisnurgana meditsiinilisse rehabi**, mitte vastupidi.

### 1.4. Üldhinne

**Valdkonna hinne: 6,5/10.**

Positiivne: tohutu ja kasvav probleem (EL-i töötervishoiu MSK-kulud hinnanguliselt ~€240 miljardit ehk kuni 2% SKP-st `[F]`), tugev struktuurne surve (füsioterapeutide puudus, NHS-i MSK-järjekorras 372 560 inimest augustis 2025 `[F]`), ja tõestatud tehnoloogiabaas.

Negatiivne: kõige suurem segment (digital MSK: Hinge Health, Sword Health) on juba konsolideerunud ja kapitalinõudlik; sportlaste jälgimise segment on samuti konsolideerunud (Teamworks, Catapult, VALD); ja kõige lihtsam AI-toode (kliiniline scribe) muutub kommoditeediks kiiremini kui väike startup jõuab kaevikut ehitada.

**Reaalne võimalus väikesele startupile on kitsas, aga olemas** — ja see asub kliiniku töövoos, mitte sportlase telefonis.

---

# 2. Kõige olulisemad turu tähelepanekud

## 2.1. Digital MSK turg on suur, kasvab kiiresti ja on uustulnukale sisuliselt suletud

| Ettevõte | Näitaja | Allikas |
|---|---|---|
| Hinge Health | 2024 tulu $390M (+33%); IPO mai 2025 hinnaga $32/aktsia; Q1 2026 tulu $182M (+47% YoY); 2026 prognoos ~$732M | `[F]` börsi- ja meediaaruanded |
| Sword Health | $40M raund juuni 2025 hinnanguga $4B; kokku ~$450M kaasatud; ostis Kaia Health'i jaan 2026 $285M eest | `[F]` |
| Kaia Health | Iseseisvana ei suutnud konkureerida; ostetud Swordi poolt | `[F]` |

**Tõlgendus `[H]`:** see on turg, kus võitjad on juba selgunud ja kus võistlus käib USA tööandjate ja kindlustusandjate kanali pärast. Sword rahastab Euroopa laienemist (Saksamaa DiGA, UK) Kaia ostuga. **Uus startup, kes tahab olla "Euroopa Hinge Health", jõuab 5 aastat hiljaks ja €200M puudu.**

Oluline nüanss ROI kohta: sõltumatu hindaja Peterson Health Technology Institute leidis, et **füsioterapeudi juhitud** virtuaalsed MSK-lahendused parandavad valu ja funktsiooni võrreldavalt kohapealse füsioteraapiaga ja vähendavad netokulusid — aga näitearvutus oli, et 25% üleminekul hinnaga $995/aastas on kokkuhoid ~$4,4M miljoni kommertskindlustatu kohta `[F]`. See on **tagasihoidlik** number, mitte revolutsioon. Ja PHTI leidis, et **puhtalt tarkvarapõhised (ilma kliinikuta) lahendused olid nõrgemad** — mis on täpselt see, mida odav startup ehitada suudaks.

## 2.2. Sportlaste jälgimise (athlete monitoring) turg on väike ja konsolideerunud

| Ettevõte | Tulu / seis | Allikas |
|---|---|---|
| Catapult Sports | TTM tulu ~$141M (märts 2026) | `[F]` börsiandmed |
| VALD Performance | ~$54M aastatulu (2026) | `[V]/[H]` Tracxn — kolmanda osapoole hinnang, mitte auditeeritud |
| Teamworks | Ostis Smartabase'i (2023), lisaks 3 muud ettevõtet; positsioneerib end "sports operating system'ina" | `[F]` |
| Kitman Labs | Performance Intelligence platvorm, kasutusel NFL/MLB/NHL/ragbi | `[F]` |

**Tähelepanek `[H]`:** kogu globaalne athlete monitoring segment on suurusjärgus **mõnisada miljonit dollarit aastatulu** — see on väiksem kui üks keskmine B2B SaaS vertikaal. Catapult, mis on kategoorias suurim, teeb $141M. Võrdluseks: Hinge Health üksi teeb 5× rohkem.

**Järeldus:** profisport ei ole turg, kuhu ehitada suurt ettevõtet. See on turg, kust saada usaldusväärsust.

## 2.3. Kliinikutarkvara turg on Euroopas fragmenteeritud — see on hea ja halb

Euroopa moodustab ~27,6% globaalsest füsioteraapiatarkvara tulust; Euroopa turul on **fragmenteeritum tarnijamaastik**, kus riigipõhised regulatiivsed nõuded ja keele lokaliseerimine loovad barjääre, mis soosivad kohalikke/regionaalseid pakkujaid `[V]` (turuanalüüsi allikas, mitte auditeeritud).

**Tõlgendus `[H]`:** see on struktuurselt hea väikesele Euroopa startupile — USA hiiglane (WebPT) ei domineeri Euroopat. Aga see tähendab ka, et **iga riik on eraldi müügipingutus** ja skaleerimine on aeglane.

## 2.4. Puhas harjutuste määramise / adherentsuse tarkvara on tõestatult **halb äri**

See on analüüsi kõige olulisem negatiivne signaal.

**Physitrack Plc** (Nasdaq First North, PTRK) — maailma tuntuim "remote exercise prescription + patient engagement" platvorm:
- 2025. aasta tulu ~13,5M (–2,5% YoY, ehk **kahanev**) `[F]`
- Kahjum kasvas –8,71M-ni (34,9% suurem kui 2024) `[F]`
- Turukapitalisatsioon ~$13,8M aktsiahinnaga ~$0,85 (august 2026) `[F]`

**See on ettevõte, mis tegi täpselt selle toote, mida enamik "AI füsioteraapia" ideid kirjeldab — ja turg hindab teda vähem kui ühe aasta tulu.** `[H]` Kui te ehitate koduharjutuste rakendust videote ja adherentsuse jälgimisega, siis Physitracki finantsid on teie parim ennustus tulemuse kohta.

## 2.5. AI-kirjutaja (scribe) turg on kiireim, aga ka kõige kiiremini kommoditiseeruv

Rahastus 2026. aasta jooksul: Abridge $300M+ Series E hinnanguga $5,3B; Ambience $243M; Nabla $70M; Heidi $65M hinnanguga $465M `[F]`.

**Tähelepanek `[H]`:** see tähendab kahte asja korraga. (a) Ostjad **maksavad** dokumentatsiooni automatiseerimise eest — nõudlus on tõestatud. (b) Üldine arstikeskne scribe on kaotatud lahing väikesele tiimile. **Võimalus on vertikaalis, mida hiiglased ei optimeeri** — ja füsioteraapia töövoog erineb arsti omast fundamentaalselt (vt ptk 5).

## 2.6. Regulatiivne aken on praegu ebatavaliselt soodne

EL AI Act'i kõrge riskiga kohustused reguleeritud toodetele (sh meditsiiniseadmed, Annex I) lükkusid Digital Omnibus'e paketiga edasi **2. augustini 2028**; iseseisvate Annex III süsteemide tähtaeg on 2. detsember 2027 `[F]` (seis 2026. aasta keskpaik).

**Tõlgendus `[H]`:** see annab ~2 aastat, mille jooksul saab ehitada mitte-meditsiiniseadme (dokumentatsioon, töövoog, mõõtmine) toote, koguda andmeid ja tulemusi, ning otsustada alles siis, kas minna MDR-i teed.

## 2.7. Struktuurne surve on reaalne ja püsiv

- Iga kolmas eurooplane teatab luu- ja lihaskonna probleemist — kokku ~150 miljonit inimest `[F]`
- Töösuhtelised MSK-häired: hinnanguliselt ~€240 miljardit ehk kuni 2% SKP-st; 40–50% kõigist tööga seotud terviseprobleemide kuludest `[F]`
- NHS-i MSK-füsioteraapia järjekord: 372 560 inimest (august 2025); Šotimaal nähti 4 nädala jooksul vaid 47,6% patsientidest `[F]`
- Euroopa profijalgpall: vigastused maksid top-5 liigade klubidele 5 hooaja jooksul €3,45 miljardit; 2024/25 hooajal €676M `[F]`

**Nõudlus ei ole probleem. Maksja ja töövoog on probleem.** `[H]`

---

# 3. Kõige suuremad lahendamata probleemid

Alustan probleemidest, mitte lahendustest. Iga probleemi juures on hinnatud kõik nõutud dimensioonid.

## P1. Kliiniline dokumentatsioon sööb füsioterapeudi päevast suure osa

| Dimensioon | Hinnang |
|---|---|
| **Kes kogeb** | Füsioterapeut, tegevusterapeut, spordiarst, kliinikuomanik |
| **Kui tihti** | Iga patsiendikontakti järel — 15–25 korda päevas ambulatoorses kliinikus |
| **Kui kallis** | Tööstuse allikad hindavad 8–15 min dokumentatsiooni kontakti kohta `[V]`; üks Euroopa tarnija väidab 30–50% tööpäevast `[V]`. **Kriitiline märkus: need on vendorite numbrid, mitte sõltumatud uuringud.** Sõltumatu, retsenseeritud number füsioteraapia kohta Euroopas puudub — see on **lünk, mille valideerimine on esimene ülesanne** |
| **Kuidas täna lahendatakse** | Käsitsi kirjutamine sessiooni ajal või pärast tööpäeva; mallid; dikteerimine |
| **Manuaalne töö** | Väga kõrge, 100% |
| **Otsene rahaline kahju** | Jah — dokumenteerimisele kuluv aeg on aeg, mille eest ei saa arvet esitada. UK andmetel toodab kõrge administratiivse toega kliinik £70 871 tulu kliiniku kohta vs £57 000 madala toega `[V]` (üksik tööstuse benchmark, mitte auditeeritud) |
| **Vale otsuse ohtlikkus** | **Madal** — vale märkus on parandatav, mitte patsiendile ohtlik, kui inimene kinnitab |
| **AI paranemine** | **5–10×** ajalises mõttes selle konkreetse ülesande puhul |
| **Ostja** | Kliinikuomanik / praktika juht |
| **Kasutaja** | Füsioterapeut |
| **Sama inimene?** | **Väikeses kliinikus JAH** (omanik ravib ka ise) — see on ostutsükli mõttes tohutu eelis |

## P2. Koduharjutuste mittetäitmine (adherence)

| Dimensioon | Hinnang |
|---|---|
| **Kes kogeb** | Patsient, füsioterapeut, maksja |
| **Kui tihti** | Iga episoodi jooksul, pidevalt |
| **Kui kallis** | Süstemaatilised ülevaated: keskmine adherentsus ~67% ühes ülevaates, koond-prevalents **21%** teises; mitte-adherentsus **kuni 70%**, tüüpiliselt 30–50% MSK-populatsioonides `[F]` |
| **Kuidas täna lahendatakse** | Paberileht, PDF, video-app, telefonikõne |
| **Manuaalne töö** | Keskmine |
| **Otsene rahaline kahju** | Kaudne — halvem tulemus, pikem episood, rohkem kordusvisiite |
| **Vale otsuse ohtlikkus** | Madal-keskmine |
| **AI paranemine** | **Ebaselge, ilmselt 1,2–2×.** Physitracki finantsid `[F]` viitavad, et see probleem **on juba adresseeritud ja turg ei maksa selle eest palju.** Adherentsus on käitumuslik, mitte informatsiooniline probleem — AI ei lahenda motivatsiooni |
| **Ostja** | Kliinik või maksja |
| **Kasutaja** | Patsient |
| **Sama inimene?** | Ei — **klassikaline B2B2C probleem** |

## P3. Patsiendi väljalangevus ja no-show

| Dimensioon | Hinnang |
|---|---|
| **Kes kogeb** | Kliinikuomanik (rahaliselt), terapeut (ajaliselt) |
| **Kui tihti** | Pidevalt |
| **Kui kallis** | No-show/tühistamise määrad füsioteraapias **10–73%**, potentsiaalne tulukadu kuni **50,6%** `[F]`. Suures ~445 000 patsiendi USA uuringus jättis **73% vähemalt ühe MSK-visiidi vahele** `[F]`. Patsiendid, kes jätavad esimese 4 nädala jooksul >20% visiitidest vahele, on **3,5× tõenäolisemad katkestama** `[F]` |
| **Kuidas täna lahendatakse** | SMS-meeldetuletused, administraatori kõned |
| **Manuaalne töö** | Keskmine-kõrge |
| **Otsene rahaline kahju** | **JAH, otsene ja arvutatav** — iga vahelejäänud slot on ~€50–80 kaotatud tulu |
| **Vale otsuse ohtlikkus** | Madal |
| **AI paranemine** | 2× (riskiennustus + automaatne sekkumine on lahendatav probleem, sest sildistatud andmed on kalendris olemas) |
| **Ostja** | Kliinikuomanik |
| **Kasutaja** | Administraator + terapeut |
| **Sama inimene?** | Väikeses kliinikus sisuliselt jah |

## P4. Objektiivsete mõõtmiste puudumine ja PROM-ide kogumine

| Dimensioon | Hinnang |
|---|---|
| **Kes kogeb** | Füsioterapeut, kliinik, maksja, teadlane |
| **Kui tihti** | Iga episoodi algus/lõpp |
| **Kui kallis** | PROM-ide vastamismäärad kliinilistes osakondades **29–42%** `[F]`; PROM-ide kasutamine füsioteraapias on madal, eriti psühhosotsiaalsete faktorite osas `[F]`; üldised PROM-id lisavad koormust ilma selge lisaväärtuseta `[F]` |
| **Kuidas täna lahendatakse** | Paberankeedid, käsitsi sisestus, sageli üldse mitte |
| **Manuaalne töö** | Kõrge |
| **Otsene rahaline kahju** | Kaudne täna, **otsene homme** (value-based lepingud, tööandjate ja kindlustuse aruandlus) |
| **Vale otsuse ohtlikkus** | Madal |
| **AI paranemine** | 3–5× (automaatne kogumine + vestlusest ekstraheerimine + kaameramõõtmine) |
| **Ostja** | Kliinik, ahel, maksja |
| **Kasutaja** | Terapeut |
| **Sama inimene?** | Osaliselt |

## P5. Vigastusriski hindamine profispordis

| Dimensioon | Hinnang |
|---|---|
| **Kes kogeb** | Spordimeeskonna meditsiini- ja sooritusstaap |
| **Kui tihti** | Iga päev |
| **Kui kallis** | **Väga kallis:** €3,45 mld 5 hooaja jooksul Euroopa top-5 liigades; 2024/25 €676M `[F]`. Premier League'i klubid maksid vigastatud mängijatele üle £1 mld palka 5 aastaga `[F]` |
| **Kuidas täna lahendatakse** | GPS + wearable + subjektiivsed küsimustikud + staabi kogemus; AMS-platvormid (Kitman, Smartabase) |
| **Manuaalne töö** | Kõrge (andmete koondamine, käsitsi raportid) |
| **Otsene rahaline kahju** | Jah, tohutu |
| **Vale otsuse ohtlikkus** | **Kõrge mõlemas suunas** — vale positiivne = tähtsa mängija puhkusele saatmine, vale negatiivne = vigastus |
| **AI paranemine** | **Ennustuses: praktiliselt 1× (tõendus puudub).** Andmete koondamises ja raporteerimises: 3–5× |
| **Ostja** | Klubi (sportdirektor / performance juht) |
| **Kasutaja** | Füsioterapeut, S&C treener, arst |
| **Sama inimene?** | Ei |
| **Kriitiline märkus** | Vaata ptk 4 — **ennustuse tõendusbaas on nõrk**. Kogu segment ostab midagi, mille tõhusust ei ole sõltumatult tõestatud |

## P6. Return-to-play / return-to-work otsus ja selle dokumenteerimine

| Dimensioon | Hinnang |
|---|---|
| **Kes kogeb** | Spordiarst, füsioterapeut, klubi, kindlustus, tööandja |
| **Kui tihti** | Iga oluline vigastus (ACL: ~6–12 kuud protsessi) |
| **Kui kallis** | Teine ACL-vigastus: koond-esinemissagedus **16,9%**, alla 25-aastastel **23%** `[F]`. Enne 9 kuud naasmine → **~7× kõrgem korduvvigastuse määr** `[F]` |
| **Kuidas täna lahendatakse** | Testipatarei (hüppetestid, isokineetika), kliiniline hinnang, ajaline kriteerium |
| **Manuaalne töö** | Kõrge |
| **Otsene rahaline kahju** | Jah — korduv operatsioon, kaotatud hooaeg, kindlustusnõue |
| **Vale otsuse ohtlikkus** | **Väga kõrge** |
| **AI paranemine** | **Otsuse kvaliteedis: teadmata/madal** (kriteeriumid ise ei ennusta kordusvigastust `[F]`). **Otsuse dokumenteerimises ja jälgitavuses: 5×** |
| **Ostja** | Kliinik, klubi, kindlustus |
| **Kasutaja** | Arst + füsioterapeut |
| **Sama inimene?** | Ei |
| **Oluline nüanss `[H]`** | Kuna kriteeriumid ei ennusta tulemust, on **peamine väärtus juriidiline ja protsessiline**: näidata, et otsus tehti korrektselt ja andmepõhiselt. See on **väiksem, aga palju kindlam ärivõimalus** kui "AI ütleb, millal naasta" |

## P7. Info liikumine sportlase, kliiniku, klubi ja treeneri vahel

| Dimensioon | Hinnang |
|---|---|
| **Kes kogeb** | Sportlane, klubi füsioterapeut, väline kliinik, treener |
| **Kui tihti** | Iga vigastuse puhul |
| **Kui kallis** | Kvalitatiivne uuring UK spordifüsioterapeutidest: kasutatakse laia hulka andmeid, aga **andmekvaliteedile pööratakse piiratud tähelepanu** `[F]`; ravi käib mitme pakkuja vahel ja kommunikatsioon on ohutuse eeldus `[F]` |
| **Kuidas täna lahendatakse** | WhatsApp, e-mail, Exceli tabelid, telefonikõned |
| **Manuaalne töö** | Kõrge |
| **Otsene rahaline kahju** | Kaudne |
| **Vale otsuse ohtlikkus** | Keskmine-kõrge |
| **AI paranemine** | 2–3× |
| **Ostja** | Klubi või kliinik |
| **Kasutaja** | Mõlemad pooled |
| **Sama inimene?** | Ei — **see on probleemi tuum: kaks organisatsiooni, üks patsient, null jagatud süsteemi** |

## P8. Kliiniku läbilaskevõime ja triaaž (avalik sektor)

| Dimensioon | Hinnang |
|---|---|
| **Kes kogeb** | Haigla/tervishoiusüsteem, patsient |
| **Kui tihti** | Pidevalt |
| **Kui kallis** | NHS MSK-järjekord 372 560 (08/2025) `[F]`; Šotimaal 47,6% 4 nädala sees `[F]` |
| **Kuidas täna lahendatakse** | Käsitsi saatekirjade sortimine, first-contact physio |
| **Manuaalne töö** | Kõrge |
| **Otsene rahaline kahju** | Süsteemne |
| **Vale otsuse ohtlikkus** | **KÕRGE** — LLM-id näitavad punaste lippude stsenaariumides **prompt-sõltuvat alatriaaži**, ehk kiireloomulise seisundi klassifitseerimist healoomuliseks `[F]` |
| **AI paranemine** | Potentsiaalselt 5×, aga **regulatiivselt ja ohutuse mõttes kõige raskem asi kogu nimekirjas** |
| **Ostja** | Riiklik tervishoiusüsteem |
| **Kasutaja** | Triaažiterapeut |
| **Sama inimene?** | Ei — ja müügitsükkel on 12–24+ kuud |

## Probleemide kokkuvõttev pingerida (sagedus × kulu × manuaalsus × mõõdetav ROI)

| # | Probleem | Sagedus | Kulu | Manuaalsus | ROI mõõdetavus | AI eelis | **Kokku** |
|---|---|---|---|---|---|---|---|
| P1 | Dokumentatsioon | 10 | 7 | 10 | 9 | 9 | **45** |
| P3 | Dropout / no-show | 9 | 8 | 6 | 10 | 6 | **39** |
| P4 | Mõõtmine / PROM | 8 | 6 | 8 | 7 | 7 | **36** |
| P6 | RTP dokumentatsioon | 4 | 9 | 8 | 5 | 6 | **32** |
| P7 | Info liikumine | 6 | 6 | 8 | 4 | 6 | **30** |
| P2 | Adherentsus | 10 | 6 | 5 | 5 | 3 | **29** |
| P5 | Vigastusennustus | 10 | 10 | 7 | 2 | **2** | **31** |
| P8 | Triaaž | 8 | 9 | 8 | 6 | 5 | **36** (aga regulatiivne risk tapab) |

**Peamine leid:** P1 võidab selgelt, sest see on ainus probleem, kus **sagedus, manuaalsus, mõõdetav ROI ja AI eelis on korraga kõrged ning vale vastuse risk on madal.**

---

# 4. Mis päriselt töötab vs mis on hype

Klassifitseerin nõutud A/B/C/D skaalal. **Ettevõtete enda turundust ei ole kusagil kasutatud tõendina.**

## A. Kliiniliselt hästi tõestatud

| Väide | Tõendus |
|---|---|
| **Telerehabilitatsioon on mitte-halvem kui kohapealne ravi** valitud MSK-seisundite puhul | PEAK non-inferiority RCT (Lancet) kroonilise põlvevalu kohta: videokonsultatsioon vs kohapealne, 5 konsultatsiooni 3 kuu jooksul. Lisaks non-inferiority RCT degeneratiivse meniskirebendi kohta (KOOS, SF-36, funktsionaalsed testid — statistiliselt olulisi erinevusi ei olnud), koos olulise kulusäästuga `[F]` |
| **Harjutuspõhised vigastuste ennetusprogrammid vähendavad vigastusi ~40–50%** | Meta-analüüsi tasemel tõendus jalgpallis; **AGA rakendamine on nii amatöör- kui profitasemel madal** `[F]` |
| **Markerless pose estimation annab kliiniliselt kasutatava täpsuse alajäseme kinemaatikas** | Süstemaatiline ülevaade 3D markerless vs marker-based: MAE üldiselt <5°, marker-põhiste süsteemide enda ebatäpsuse (pehmete kudede artefakt, markerite asetuse varieeruvus) suurusjärgus `[F]` |
| **Varajane naasmine spordi juurde suurendab korduvvigastuse riski** | Naasmine enne 9 kuud pärast ACL-rekonstruktsiooni: ~**7× kõrgem** teise ACL-vigastuse määr `[F]` |
| **Wearable'ite füsioloogiline toorsignaal (RHR, HRV) on täpne** | Valideerimisuuring EKG vastu: Oura Gen4 HRV CCC = 0,99; WHOOP CCC = 0,94 `[F]` |

## B. Paljulubav, kuid tõendus nõrk

| Väide | Tõendus |
|---|---|
| **Computer vision reaalajas tagasiside parandab rehabilitatsiooni tulemusi** | Olemas on RCT-d: CV-põhine harjutusrakendus põlveliigese artroosi puhul (JMIR mHealth, 2025) ja AI-põhine koduharjutusrakendus rotator cuff valu puhul (n=46). **Valimid on väikesed, uuringud värsked, tulemused ei ole veel korratud.** `[F]` — tõendus on olemas, aga õhuke |
| **LLM-id kliinilise otsuse toena MSK-rehabis** | Testitud, aga tulemused ebaühtlased: 10 LLM-i testis ainult 2 ületasid 90% täpsust; enamik uuringuid piirdub kokkuvõtete ja eksamiküsimustega, näidates piiranguid kliinilises arutluses ja patsiendispetsiifilistes soovitustes `[F]` |
| **Camera-based ROM mõõtmine kliinilises rutiinis** | Reliaablus/valiidsus puusa ja põlve ROM-i jaoks uuritud, tulemused paljulubavad; Exer AI on kasutusel Mayo Clinicus (aug 2026) `[F]` — **institutsionaalne kasutuselevõtt ≠ tulemuste tõendus** |
| **Digital MSK vähendab tervishoiukulusid** | PHTI sõltumatu hindamine: füsioterapeudi juhitud lahendused parandavad tulemusi võrreldavalt ja vähendavad netokulusid `[F]`, aga hinnanguline sääst on tagasihoidlik ja sõltub hinnast |

## C. Peamiselt turundus/hype

| Väide | Miks see on hype |
|---|---|
| **"Meie AI ennustab vigastusi X% täpsusega"** | Vendorite avaldatud numbrid (nt 72% täpsus, "40% vigastuste vähenemine esimesel aastal") pärinevad ettevõtete enda case-study'dest ja klubide tunnistustest `[V]`. Puudub sõltumatu, eelregistreeritud, kontrollrühmaga uuring. Klubide vigastusnumbrite muutus on tugevalt segatud kaadrimuutuste, mängukalendri, treeneri vahetuse ja **regressiooniga keskmise poole** (klubi ostab lahenduse pärast halba hooaega) `[H]` |
| **Wearable'ite "recovery score" / "readiness score"** | Aluseks olev HR/HRV on täpne, aga **liitskoorid on valideerimata mustad kastid**; algoritme uuendatakse perioodiliselt ilma läbipaistvuseta `[F]` |
| **"AI personaaltreener asendab treenerit"** | Puudub tõendus, et see muudab käitumist paremini kui olemasolevad lahendused; B2C fitness on kõrge churniga turg `[H]` |
| **AI-genereeritud rehab-plaanid ilma spetsialisti kinnituseta** | LLM-ide hindamine harjutusprogrammide genereerimisel näitab piiranguid patsiendispetsiifilisuses `[F]` |

## D. Teadus näitab, et lähenemine EI tööta hästi

**See on kõige olulisem osa kogu raportist.**

| Väide | Tõendus vastu |
|---|---|
| **Acute:Chronic Workload Ratio ennustab vigastusi** | ACWR on **matemaatiliselt seotud** (viimane nädal sisaldub nii acute kui chronic arvutuses → kunstlik korrelatsioon ~r=0,5); suhtarv moonutab andmeid madala chronic load'i korral; algsed uuringud olid tõenäoliselt alavõimsad; tulemused on vastuolulised (kõrge ACWR suurendab riski / vähendab riski / ei ole seost). Uuem töö soovitab **raamistiku kõrvale heita** `[F]` |
| **Functional Movement Screen tuvastab vigastusriskiga sportlased** | Meta-analüüs: hea inter-/intrarater reliaablus, **aga sisemise ja välise valiidsuse vead**; metodoloogilised ja statistilised piirangud takistavad ennustusvaliidsuse tuvastamist `[F]` |
| **Return-to-sport kriteeriumide läbimine vähendab kordusvigastuse riski** | Kriteeriumipõhised RTS-otsused **ei olnud seotud** teise ACL-vigastuse riskiga; teise vigastuse esinemissagedus ei erinenud kõik kriteeriumid läbinutel (28,6%) ja vähemalt ühes läbi kukkunutel (19,7%); sümmeetriline lihasjõud ei olnud seotud uue ACL-vigastusega; püsivad põlve fleksiooni jõudefitsiidid RTS-i hetkel ei olnud seotud teise vigastusega `[F]` |
| **ML on vigastusennustuses parem kui klassikaline statistika** | Süstemaatilised ülevaated: ML ei ole alati parem kui logistiline regressioon; mõned uuringud raporteerivad LR-i kõrgemat AUC-d, **kusjuures mõlemal oli halb eristusvõime** `[F]` |

### Mida see praktikas tähendab `[H]`

1. **Iga toode, mille põhilubadus on "me ennustame vigastuse", on ehitatud liivale.** Mitte sellepärast, et mudelid oleksid halvasti tehtud, vaid sellepärast, et **vigastus on suures osas juhuslik sündmus** (kontakt, õnnetus) ja mittejuhuslik osa on multifaktoriaalne ning nõrgalt mõõdetav.
2. **See on ka konkurentsieelis skeptilisele asutajale.** Turul on palju ettevõtteid, kes müüvad ennustust. Kui teie toode lubab midagi, mida saab **tegelikult tõestada** (aeg säästetud, dokument valmis, mõõtmine tehtud), siis olete pikas plaanis usaldusväärsem partner kliinikutele, kes on ühe korra juba pettunud.
3. **Kõige suurem tõestatud probleem ei ole teadmine, vaid rakendamine** — ennetusprogrammid töötavad, aga neid ei tehta; telerehab töötab, aga adherentsus on kehv. **Väärtus on kohaletoimetamises, mitte tarkuses.**

---

# 5. Existing Companies Map

Märkus: rahastus- ja tulunumbrid on avalikest allikatest; kus allikas on kolmanda osapoole hinnang (Tracxn/PitchBook), on see märgitud. **Ma ei ole ühtegi numbrit välja mõelnud; kus andmed puuduvad, on kirjas "andmed puuduvad".**

## 5.1. Digital MSK / virtuaalne füsioteraapia (B2B2C, maksja/tööandja)

| Ettevõte | Toode | Klient | Probleem | AI kasutus | Rahastus | Tulu / traction | Hinnastus | Geo | Tugevus | Nõrkus |
|---|---|---|---|---|---|---|---|---|---|---|
| **Hinge Health** | Digitaalne MSK-hoolduse programm | USA tööandjad, health plans | MSK-kulud | Motion tracking, care-team tugi | Avalik (NYSE, IPO 05/2025 @$32) | 2024 $390M; Q1 2026 $182M (+47%); 2026 guidance ~$732M `[F]` | Per-member lepingud, andmed piiratud | USA, laienemine Kanadasse/UK-sse | Skaala, kasumlikkuse pöördepunkt | Sõltuvus USA tööandjaturust |
| **Sword Health** | AI + kliiniku hübriid MSK, pelvic, Mind | Tööandjad, maksjad | Sama | Digital therapist "Phoenix", motion tracking | ~$450M kokku; $40M @ $4B (06/2025) `[F]` | Ei avalikusta; IPO võimalik ~2028 `[V]` | Andmed puuduvad | USA + EU (PT päritolu, DE DiGA, UK) | Euroopa jalajälg, hübriidmudel | Erakäes, hindamine kõrge |
| **Kaia Health** | Motion-tracking MSK app (DiGA) | DE payers, USA tööandjad | Seljavalu, MSK | Pose estimation | Ostetud $285M (01/2026) `[F]` | Ei suutnud iseseisvalt konkureerida | DiGA hind | DE, USA | DiGA staatus | **Kergem "software-first" mudel osutus nõrgemaks kui kliinikuga hübriid** |
| **Physitrack** | Harjutuste määramine, telehealth, RTM | Kliinikud, terapeudid | HEP + engagement | Piiratud | Börsil (Nasdaq First North) | Tulu ~13,5M (2025, –2,5%); kahjum –8,7M; mcap ~$14M `[F]` | Per-seat SaaS | Globaalne, EU tugev | Suur kasutajabaas | **Kahanev tulu, väike hindamine — hoiatav näide** |

## 5.2. Sportlaste jälgimine ja soorituse platvormid (B2B, klubid)

| Ettevõte | Toode | Klient | Probleem | AI kasutus | Rahastus/staatus | Traction | Geo | Tugevus | Nõrkus |
|---|---|---|---|---|---|---|---|---|---|
| **Catapult Sports** | GPS/IMU wearables + video + analüütika | Profiklubid, kolledžid | Koormus, sooritus | Signaalitöötlus, mõõdikud | Börsil (ASX) | TTM tulu ~$141M (03/2026) `[F]` | Globaalne | Turuliider riistvaras | Riistvara marginaalid, kasvupiirid |
| **Kitman Labs** | Performance Intelligence / AMS | NFL, MLB, NHL, ragbi, jalgpall | Andmete killustatus | Analüütika, riskimudelid | Erakäes | Andmed puuduvad | Globaalne | Sügav integratsioon | Sales cycle pikk |
| **Teamworks (Smartabase)** | "Operating system for sports" | Klubid, ülikoolid, sõjavägi | Kogu klubi töövoog | Töövoogude automatiseerimine | Erakäes; ostis Smartabase 2023 + 3 muud `[F]` | Andmed puuduvad | USA-keskne | Konsolideerija | Sulgeb turu uustulnukale |
| **VALD Performance** | ForceDecks, NordBord, ForceFrame, HumanTrak | Klubid, kliinikud, ülikoolid | Objektiivne jõu-/liikumismõõtmine | Signaalianalüüs | Erakäes | ~$54M tulu (2026) `[V]` Tracxn hinnang | Globaalne | **Liigub sporditurult kliinikuturule** | Riistvarasõltuvus |
| **Zone7** | Vigastusriski prognoos | Jalgpalliklubid | Vigastused | Deep learning ajaseeriatel | Erakäes | Klubide arv ja "täpsus" pärinevad ettevõtte materjalidest `[V]` | EU/globaalne | Bränd kategoorias | **Sõltumatu valideerimine puudub** |
| **Sportlyzer** (EE) | Klubi- ja treeningkorraldus | Noorte- ja amatöörklubid | Administratsioon | Piiratud | ~$1,05M kaasatud `[F]` | 17 000+ klubi loodud, 100+ riiki `[V]` | EE → globaalne | **Eesti näide, et amatöörsegment on ligipääsetav** | Madal ACV segment |

## 5.3. Computer vision / liikumise hindamine kliinilises kontekstis

| Ettevõte | Toode | Klient | AI kasutus | Rahastus | Traction | Tugevus | Nõrkus |
|---|---|---|---|---|---|---|---|
| **Exer AI (Exer Labs)** | Exer Scan — kaamerapõhine liigeste liikuvuse hindamine | Haiglad, ortopeedia (Mayo Clinic) | Pose estimation, ROM | ~$11M kokku `[F]` | Mayo Clinic juurutus (08/2026); plaanib sports medicine mooduli 2026 lõpp/2027 algus `[F]` | **Tõestab, et haiglad ostavad kaamerapõhist mõõtmist** | Väike rahastus vs ambitsioon; USA-keskne |
| **Kemtai** | CV-põhine harjutuste platvorm, reaalajas korrektsioon | Kliinikud, maksjad, digitaalsed platvormid | Neuraalvõrgud liikumise analüüsiks | Seed `[F]` | Andmed puuduvad | Ei nõua riistvara | Väike; konkureerib Physitracki hinnasurvega |

## 5.4. Kliiniline dokumentatsioon / AI scribe

| Ettevõte | Fookus | Rahastus 2026 | Märkus |
|---|---|---|---|
| **Abridge** | Arstid, USA haiglad | $300M+ Series E, hinnang $5,3B `[F]` | Kategooria liider |
| **Ambience Healthcare** | Haiglad | $243M `[F]` | |
| **Nabla** | Ambient, EHR | $70M Series C `[F]` | |
| **Heidi Health** | UK esmatasand, laialdaselt kasutusel | $65M @ $465M `[F]` | Tugev UK positsioon |
| **Tandem Health** | Euroopa, väidab MDR Class IIa sertifikaati | Andmed puuduvad | `[V]` ettevõtte enda väide; **oluline signaal, et Euroopas liigutakse meditsiiniseadme suunas** |

## 5.5. Kus konkurents on üllatavalt VÄIKE `[H]`

1. **Füsioteraapia-spetsiifiline (mitte arstikeskne) dokumentatsioon ja episoodi-tasemel struktureerimine Euroopas.** Suured scribe'id optimeerivad arsti-patsiendi ühekordset konsultatsiooni ja USA kodeerimist. Füsioteraapia episood on 5–6 seanssi keskmiselt `[V]` ja väärtus on **progressioonis üle seansside**, mitte ühes märkmes.
2. **Spordimeditsiini rehabikliinikud** (post-op ACL, õlg, hüppeliiges) kui eraldi ostjasegment — Exer AI alles plaanib sinna siseneda `[F]`.
3. **Väikeste ja keskmiste klubide/akadeemiate meditsiiniline dokumentatsioon** — Teamworks/Kitman teenindavad tippu, all on tühjus (Sportlyzer katab administratsiooni, mitte meditsiini).
4. **Aruandlus maksjale/tööandjale/kindlustusele Euroopa kontekstis** — DiGA-järgne maailm, occupational health, tööandja-rahastatud teenused.

---

# 6. Töövoo analüüs

## 6.1. Füsioterapeudi töövoog — kus AI päriselt aitab

| # | Etapp | Kas AI automatiseerib? | Kas AI abistab? | Ajasääst | Vajalik info | Vea risk | Inimene peab kinnitama? |
|---|---|---|---|---|---|---|---|
| 1 | Anamnees | Osaliselt (eelankeet, struktureerimine) | Jah | 5–10 min/patsient | Patsiendi vastused, ajalugu | Madal | Jah |
| 2 | Patsiendi hindamine | **Ei** — käed patsiendil | Jah (märkmete kogumine kõnest) | 5–8 min | Heli, kontekst | Madal | Jah |
| 3 | Liikuvuse testimine | Osaliselt (kaamera-ROM) | Jah | 3–5 min + parem korduvus | Video | Keskmine | Jah |
| 4 | Jõutestid | Ei (nõuab riistvara) | Jah (andmete automaatne salvestus) | 2–5 min | Dünamomeeter, jõuplatvorm | Keskmine | Jah |
| 5 | Video / liigutuse vaatlus | Osaliselt | Jah (kvantifitseerimine) | 10–30 min kui täna tehakse käsitsi | Video | Keskmine | Jah |
| 6 | Diagnoosi hüpotees | **EI** — regulatiivne ja ohutuse piir | Piiratult (diferentsiaaldiagnoosi meeldetuletus) | — | Kõik ülal | **KÕRGE** (punaste lippude alatriaaž `[F]`) | **Kohustuslik** |
| 7 | Taastusraviplaani koostamine | Osaliselt (mustand) | **Jah — tugev kandidaat** | 5–15 min | Hinnang + eesmärgid | Keskmine | Jah |
| 8 | Harjutuste õpetamine | Ei | Jah (materjalide genereerimine, keeled) | 3–5 min | Plaan | Madal | Jah |
| 9 | Progressi jälgimine | **Jah — tugev kandidaat** | Jah | 5–10 min/nädal | Seansside andmed, PROM-id | Madal | Osaliselt |
| 10 | **Dokumentatsioon** | **JAH — tugevaim kandidaat** | Jah | **8–15 min/kontakt** `[V]` | Heli + struktuur | **Madal** | Jah (kiire ülevaatus) |
| 11 | Follow-up | Jah (automaatika, riskipõhine) | Jah | Administratiivne aeg | Kalender, adherentsus | Madal | Ei |
| 12 | Return-to-sport otsus | **EI** | Jah (andmete koondamine + dokument) | 20–60 min raporti kohta | Kogu episood | **KÕRGE** | **Kohustuslik** |

**Muster:** AI väärtus on **kõrge etappides 1, 9, 10, 11** (info kogumine, struktureerimine, liigutamine) ja **madal või ohtlik etappides 6 ja 12** (kliiniline otsus). See on täpselt vastupidine sellele, mida enamik "AI füsioterapeut" pitch'e lubab.

## 6.2. Profitreeneri / spordimeeskonna töövoog

| Etapp | AI automatiseerib? | Ajasääst | Vea risk | Kommentaar |
|---|---|---|---|---|
| Treeningkoormuse planeerimine | Osaliselt | Keskmine | Keskmine | Treener ei loovuta seda |
| GPS/wearable andmete kogumine ja puhastamine | **Jah** | **Suur** — täna käsitsi Excelis | Madal | **Kõige alahinnatum ülesanne** |
| Igapäevane "kes on saadaval" raport | **Jah** | 30–60 min/päev | Madal | Klassikaline back-office wedge |
| Vigastusriski hinnang | Formaalselt jah, **sisuliselt ei tööta** `[F]` | — | **Kõrge** | Vt ptk 4D |
| Medical–performance kommunikatsioon | Osaliselt | Keskmine | Keskmine | Kaks organisatsiooni, üks sportlane |
| Rehabis oleva mängija progress | Jah | Keskmine | Madal | |
| RTP otsus | Ei | — | Kõrge | Arsti otsus |
| Aruandlus juhtkonnale / omanikule | **Jah** | Suur | Madal | Alahinnatud, korduv |

---

# 7. Sport × Rehab ristumiskoht — kriitiline analüüs

Vastan otse igale nimekirjas olnud ideele.

| Idee | Tehniliselt realistlik? | Majanduslikult realistlik? | Verdikt |
|---|---|---|---|
| Vigastuste **varajane avastamine** | Osaliselt (mõõdetavad muutused) | Ostja ebaselge | ⚠️ Nõrk |
| **Vigastusriski prognoos** | Jah tehniliselt, **ei sisuliselt** `[F]` | Ostjad on olemas, aga tõendus puudub | ❌ **Vältida põhilubadusena** |
| **AI movement screening** | Jah (pose estimation MAE <5°) `[F]` | Kellele müüa? Screening'u ennustusväärtus on nõrk `[F]` | ⚠️ Mõõtmisena jah, sõelumisena ei |
| **Asümmeetriate leidmine** | Jah | Asümmeetria ≠ vigastusrisk (RTS-tõendus vastu) `[F]` | ⚠️ Metric ilma tähenduseta |
| **Automaatne biomehaaniline analüüs telefonivideost** | **Jah, tõestatud** `[F]` | Sõltub ostjast | ✅ **Tugev tehniline alus** |
| **Rehab progress tracking** | Jah | Jah — kliinik maksab | ✅ **Tugev** |
| **Automaatne harjutuste soorituse kontroll** | Jah | **Turg maksab vähe** (Physitrack) `[F]` | ⚠️ Feature, mitte ettevõte |
| **Treeningu automaatne kohandamine vigastuse järgi** | Osaliselt | Vastutus küsitav | ⚠️ |
| **Return-to-play readiness score** | Jah | **Skoor ise ei ennusta tulemust** `[F]` | ❌ Skoorina; ✅ **dokumendina** |
| **Füsioterapeudi AI copilot** | Jah | **Jah — ostja ja kasutaja on sama inimene** | ✅✅ **Tugevaim** |
| **Treeneri + füsioterapeudi ühine dashboard** | Jah | Kaks organisatsiooni = raske müük | ⚠️ |
| **Injury history + workload + wearable + video ühendamine** | Jah (integratsioonitöö) | Ainult tippklubidele, kus incumbendid on | ⚠️ |
| **Personaliseeritud recovery** | Osaliselt | Recovery-skooride tõendus nõrk `[F]` | ⚠️ |
| **Remote rehab monitoring** | Jah | RTM-kodeerimine USA-s toetab; EL-is maksja ebaselge | ⚠️ USA-s jah, EL-is nõrgem |

## Peamine järeldus ristumiskoha kohta `[H]`

**Sport × rehab ristumiskoht annab parima TOOTE, aga halvima TURU.**

- Spordipoolel: kõrge maksevalmidus üksikjuhtudel (klubi maksab hea meelega), aga **ostjaid on maailmas mõnisada** ja müügitsükkel on hooajapõhine ja poliitiline.
- Meditsiinipoolel: madalam ACV, aga **kümneid tuhandeid ostjaid**, korduv eelarve, ja probleemid on iga päev.

**Õige strateegia:** ehita meditsiinilise rehabi töövoole, kasuta spordi konteksti (post-op ACL, RTS, sportlaspatsiendid) **diferentseerijana ja bränditeravusena**, mitte peamise turuna. Spordikliinikud on **kõrgeima maksevalmidusega alamsegment meditsiinipoolel** — see on täpne koht, kus need kaks kohtuvad ilma, et peaks müüma klubidele.

---

# 8. Ärimudelite ja kliendisegmentide võrdlus

| Segment | Maksevalmidus | ACV | Müügitsükkel | Turu suurus | Regulatiivne keerukus | Kliendi leidmine | Churn | ROI mõõdetavus | Integratsioon | Vastutus |
|---|---|---|---|---|---|---|---|---|---|---|
| **B2C sportlane** | Madal | €50–200/a | Päevad | Suur | Madal | **Väga raske (CAC)** | **Väga kõrge** | Puudub | Puudub | Madal |
| **B2B treener / jõusaal** | Madal-keskmine | €300–2 000/a | Nädalad | Keskmine | Madal | Keskmine | Kõrge | Nõrk | Vähene | Madal |
| **B2B füsioteraapiakliinik** | **Keskmine-kõrge** | **€3 000–20 000/a** | **2–8 nädalat** | Suur (EU fragmenteeritud) | **Madal, kui pole meditsiiniseade** | **Hea** (väike otsustusahel) | Keskmine-madal | **Hea** (aeg, seansid, tulu) | Keskmine (PMS/EHR) | Keskmine |
| **B2B2C kindlustus / tööandja** | Kõrge | €50 000–500 000+ | **9–18 kuud** | Väga suur | Kõrge | Väga raske | Madal | Hea, aga nõuab tõendust | Kõrge | Kõrge |
| **Profisport (klubid)** | Keskmine-kõrge üksikult | €10 000–100 000/a | 3–9 kuud, hooajapõhine | **Väike (sadu ostjaid)** | Madal | Keskmine (võrgustik) | Keskmine (staabi vahetus!) | **Halb** | Kõrge | Keskmine |
| **Haigla / tervishoiusüsteem** | Kõrge | €100 000+ | **12–24+ kuud** | Väga suur | **Väga kõrge** | Väga raske | Väga madal | Keskmine | Väga kõrge | **Kõrge** |

## Soovitatav beachhead `[H]`

**Erafinantseeritud füsioteraapia- ja spordimeditsiinikliinikud, 3–15 terapeudiga, Eestis ja Põhjamaades.**

Põhjendus:
1. **Ostja = kasutaja** (omanik ravib ka ise) → müügitsükkel nädalates, mitte kvartalites
2. **ROI on arvutatav** samas valuutas, milles kliinik mõtleb: seansid päevas, tulu terapeudi kohta
3. **Madal regulatiivne risk**, kui toode jääb dokumentatsiooni/töövoo poolele
4. **Ei ole Hinge/Sword'i tee peal** — nemad müüvad maksjale, mitte kliinikule; nad on isegi potentsiaalsed partnerid
5. Fragmenteeritud Euroopa turg **soosib kohalikku pakkujat** `[V]`

**Mida vältida beachhead'ina:** B2C sportlane (CAC + churn), haigla (tsükkel), kindlustus (tõendusnõue enne tulu).

---

# 9. Regulatsioon ja risk (EL fookus)

## 9.1. Millal muutub tarkvara meditsiiniseadmeks

MDR + MDCG 2019-11 (rev 1) loogika `[F]`:
- **Fitness/wellness rakendused ei ole meditsiiniseadme tarkvara (MDSW).** MDR sätestab selle sõnaselgelt.
- MDSW on tarkvara, mis annab infot **haiguse ravi või diagnoosi eesmärgil**.
- Klassifitseerimine sõltub kahest teljest: (a) info olulisus tervishoiuolukorras, (b) patsiendi seisundi tõsidus. See on **Rule 11**, mis viib enamiku otsusetoe tarkvara **vähemalt IIa klassi**.
- Revideeritud versioon lisas selgitusi just **AI-d kasutava tarkvara**, moodulite ja EHR-integratsioonide kohta `[F]`.

### Praktiline piir `[H]`

| Funktsioon | Tõenäoline staatus |
|---|---|
| Kõnest kliinilise märkme genereerimine, mille terapeut kinnitab | **Ei ole meditsiiniseade** (dokumenteerimine, mitte diagnoos) |
| Harjutuste teegist programmi mustandi koostamine terapeudile | **Piiripealne, tõenäoliselt mitte**, kui terapeut valib ja vastutab |
| ROM-i mõõtmine kaameraga ja arvu salvestamine | **Piiripealne** — kui seda kasutatakse diagnoosiks/raviotsuseks, siis tõenäoliselt jah |
| "Teie vigastusrisk on 78%" | **Jah, meditsiiniseade** (ja tõendus puudub — topeltrisk) |
| "Patsient on valmis spordi juurde naasma" | **Jah, meditsiiniseade**, tõenäoliselt IIa+ |
| Otse patsiendile suunatud triaaž ilma kliinikuta | **Jah**, kõrge risk |

## 9.2. AI Act

- AI-süsteem, mis **ise on meditsiiniseade** või meditsiiniseadme ohutuskomponent (MDR/IVDR), on automaatselt **kõrge riskiga** (Art. 6(1), Annex I) `[F]`
- Kõrge riski kohustused Annex I toodetele: **2. august 2028**; iseseisvatele Annex III süsteemidele **2. detsember 2027** (Digital Omnibus, 2026) `[F]`
- Läbipaistvuskohustused (kasutaja teab, et suhtleb AI-ga; genereeritud sisu märgistamine) kehtivad varem ja on odavad täita

**Järeldus `[H]`:** kui toode EI ole meditsiiniseade, siis AI Act'i kõrge riski koorem ei rakendu ja jääb üldine läbipaistvus + GDPR. **See vahe on sadu tuhandeid eurosid ja 12–24 kuud.**

## 9.3. GDPR ja terviseandmed

- Terviseandmed = eriliigilised andmed (Art. 9) → vajalik selge õiguslik alus
- Kliinikule müües olete **volitatud töötleja** (processor), kliinik on vastutav töötleja → vajalik DPA, ELis hostimine, alltöötlejate nimekiri, säilitustähtajad
- **Praktiline nõue Euroopa müügis:** EL-i andmekeskus, andmete mittekasutamine mudeli treenimiseks ilma eraldi nõusolekuta, ja kirjalik vastus küsimusele "kas mudel on USA-s". `[H]` See on müügitsükli reaalne blokeerija, mitte teoreetiline.
- Eestis lisandub riiklik terviseinfosüsteem (TIS) ja X-tee kontekst — **eelis, mitte takistus** (vt ptk 12)

## 9.4. Vastutus (liability)

| Stsenaarium | Risk |
|---|---|
| Vale vigastusriski ennustus (vale negatiivne) | Sportlane vigastub → **maine- ja lepinguline risk**; meditsiiniline vastutus sõltub sellest, kas toode oli otsuse alus |
| Vale RTS-soovitus | **Kõrgeim risk kogu valdkonnas** — korduvvigastus, potentsiaalselt karjääri lõpp |
| Vale/hallutsineeritud kliiniline märge | Keskmine, **maandatav kohustusliku inimkinnitusega enne salvestamist** |
| Punase lipu vahelejätmine triaažis | **Kõrge** — LLM-ide tõestatud alatriaaži kalduvus `[F]` |

## 9.5. Madala regulatiivse riskiga ehitusstrateegia `[H]`

1. **Positsioneeri toode dokumentatsiooni- ja töövootööriistana**, mitte diagnostilise või otsustava tööriistana. Sõnastus tootedokumentatsioonis on regulatiivselt sama tähtis kui kood.
2. **Inimene kinnitab kõik**, mis läheb patsiendi kaarti. Logi kinnitus.
3. **Ära anna arvulisi riskiskoore ega valmisoleku hinnanguid** MVP-s. Anna mõõtmisi ja kokkuvõtteid.
4. **Ära suhtle otse patsiendiga kliinilistes küsimustes** enne, kui olete valmis MDR-i teele minema.
5. Ehita algusest peale: audit-logi, versioonihaldus, andmete päritolu, EL-i hosting. **See on hiljem MDR-i alus, kui otsustate minna.**
6. Kaardista tee IIa-le, aga **ära alusta sellega** — Tandem Health'i MDR IIa `[V]` näitab, et see on tehtav, aga see on hilisem samm.

---

# 10. Tehniline realistlikkus

| Vajadus | Hinnang |
|---|---|
| **Kõne → struktureeritud kliiniline märge** | Foundation model + API on **piisav**. Vajalik: domeenispetsiifiline väljundskeem, eestikeelne/soomekeelne kõnetuvastus (parimad mudelid katavad, aga meditsiiniterminoloogia vajab testimist), retrieval kliiniku enda mallidest. **Oma mudeli treenimine ei ole vajalik.** Fine-tuning võib-olla hiljem väljundvormingu jaoks |
| **Harjutusprogrammi mustand** | Foundation model + struktureeritud harjutuste teek. Ei nõua meditsiinilisi sildistatud andmeid |
| **Kaamerapõhine ROM / liikumise mõõtmine** | Olemasolevad pose estimation mudelid (MediaPipe/MoveNet klassis) + kalibratsioon. Tõenduspõhine täpsus MAE <5° alajäsemes `[F]`. **Nõuab standardiseeritud protokolli** (kaugus, nurk, valgus) — see on toote, mitte mudeli probleem |
| **Vigastusriski ennustusmudel** | **Nõuab massiivset proprietary dataseti, mida startupil ei ole, ja tõendus näitab, et isegi siis ei tööta hästi** `[F]`. **Ära ehita** |
| **Wearable integratsioon** | Mitte vajalik MVP-s. Hiljem API-de kaudu |
| **Riistvara** | **Mitte vajalik.** Telefon/tahvel piisab. See on suur eelis vs VALD (jõuplatvormid) |
| **Inference cost** | Ambient scribe: ~30–60 min heli/päev/terapeut. Praeguste API-hindadega suurusjärgus **€5–20/terapeut/kuu** `[H]` (sõltub mudelist ja pikkusest) — jätab €80–150/kuu hinnastuse juures terve marginaali |
| **Latency** | Ei ole reaalajanõue. Märge võib valmida 30–90 s pärast seanssi |
| **Täpsusnõue** | Märge peab olema **redigeeritav, mitte täiuslik**. See on kriitiline vahe vs diagnostiline toode |
| **False positive / negative** | Dokumentatsioonis: FP = liigne info (tüütu), FN = puuduv info (terapeut lisab). **Mõlemad taastatavad.** Võrdle: riskiennustuses on mõlemad kahjulikud ja mittetaastatavad |

**MVP tehniline kirjeldus:** veebirakendus + mobiil, salvestus seansi ajal (või kokkuvõttev dikteerimine pärast), transkriptsioon → struktureeritud SOAP/episoodi-märge → terapeut kinnitab → salvestub + genereerib harjutusplaani mustandi ja järgmise seansi eesmärgid. **Ehitatav 8–12 nädalaga 2 inimesega.** `[H]`

---

# 11. 32 startupiideed (kõik seotud ptk 3 probleemidega)

Iga idee juures on viide probleemile (P1–P8). Veergude lühendid: **MVP** = minimaalne toode, **Reg** = regulatiivne koorem (M/K/S = madal/keskmine/suur), **Konk** = konkurents, **ACV** = realistlik aastane lepingu väärtus, **Raskus** = 1–10.

| # | Idee | Kasutaja | Ostja | Valu (P#) | Praegune lahendus | AI eelis | MVP | Reg | Konk | ACV | Raskus |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **Rehab-native ambient scribe** (füsioteraapia episoodi-märge kõnest) | Füsioterapeut | Kliinikuomanik | P1 | Käsitsi + mallid | 5–10× ajas | Salvestus → SOAP → kinnitus | M | Keskmine (üldised scribe'id) | €3–15k | 5 |
| 2 | **Harjutusplaani mustand märkmest** | Füsioterapeut | Kliinik | P1,P2 | Käsitsi valik teegist | 3× | Märge → plaan | M | Kõrge | +€1–3k | 4 |
| 3 | **PROM-i automaatne kogumine ja tõlgendus** | Terapeut | Kliinik/maksja | P4 | Paberankeedid, 29–42% vastavus `[F]` | 3–5× | SMS/app + dashboard | M | Madal | €2–6k | 4 |
| 4 | **Dropout-riski ennustus ja automaatne tagasikutse** | Administraator | Kliinikuomanik | P3 | SMS-meeldetuletus | 2× | Kalendriandmed + mudel | M | Madal | €2–5k | 3 |
| 5 | **Väljakirjutamise / RTS-kirja generaator** | Arst, terapeut | Kliinik | P6 | 20–60 min käsitsi | 5× | Episood → dokument | M | Väga madal | €2–5k | 3 |
| 6 | **Kaamerapõhine ROM/liikuvuse mõõtmine kliinikus** | Terapeut | Kliinik | P4 | Goniomeeter, silmamõõt | 3× korduvuses | Telefon + protokoll | **K** | Keskmine (Exer AI) | €3–8k | 6 |
| 7 | **Objektiivne testipäevik** (jõu-, hüppe-, liikuvustestide automaatne salvestus) | Terapeut/S&C | Kliinik/klubi | P4,P6 | Excel | 3× | Vormid + integratsioonid | M | Madal | €2–6k | 4 |
| 8 | **Kindlustuse/maksja aruandluse pakk** (episoodi tulemuste raport) | Kliinikujuht | Kliinik | P4 | Käsitsi | 5× | Andmed → raport | M | Madal | €3–10k | 5 |
| 9 | **AI vastuvõtt / administraator kliinikule** (broneering, kordusvisiit) | Administraator | Kliinikuomanik | P3 | Telefon | 3× | Kõne/chat agent | M | **Kõrge** | €2–6k | 4 |
| 10 | **Spordimeditsiini kliiniku episoodiplatvorm** (post-op ACL rada algusest lõpuni) | Spordiarst + füsio | Kliinik | P1,P4,P6 | Killustatud | 3× | Protokolli-mootor + märkmed | K | **Madal** | €10–30k | 6 |
| 11 | **Klubi meditsiinilise dokumentatsiooni süsteem** (väikesed/keskmised klubid) | Klubi füsio | Klubi | P1,P7 | Excel, paber | 4× | Mobiilne märkmesüsteem | M | Madal (all-segmendis) | €3–10k | 5 |
| 12 | **Sportlase saadavuse (availability) raport treenerile** | Performance juht | Klubi | P5,P7 | Käsitsi koostatud | 3× | Andmed → päevaraport | M | Keskmine | €5–20k | 5 |
| 13 | **GPS/wearable andmete "janitor"** (koondamine, puhastamine, ühtlustamine) | Sporditeadlane | Klubi | P5 | Excel, käsitsi | 5× | ETL + API-d | M | Keskmine | €5–25k | 5 |
| 14 | **Video mehhanismi-klippide automaatne tuvastus** (vigastuse hetk mängus) | Meditsiinistaap | Klubi | P5,P6 | Käsitsi otsimine | 5× | Video + sündmuse tuvastus | M | Madal | €5–15k | 7 |
| 15 | **Rahvusliku/liidu vigastusregistri automatiseerimine** | Föderatsioon | Föderatsioon/liit | P5 | Käsitsi vormid | 4× | Vormid + valideerimine | M | Väga madal | €10–50k | 5 |
| 16 | **Noorteakadeemia kasvu- ja koormusmonitooring** | Akadeemia juht | Klubi/akadeemia | P5 | Paber | 2× | Mobiilne sisestus | M | Madal | €2–8k | 4 |
| 17 | **Spordikindlustuse riskihindamise andmetoode** | Kindlustusandja | Kindlustusandja | P5,P6 | Käsitsi ajalugu | 2× | Andmete standardiseerimine | K | Madal | €50k+ | 8 |
| 18 | **MSK-triaaž avaliku sektori järjekorrale** | Triaažiterapeut | Haigla/riik | P8 | Käsitsi saatekirjad | 5× (kui ohutu) | Saatekiri → prioriteet | **S** | Keskmine | €50k+ | 9 |
| 19 | **Tööandja MSK-ennetusprogramm Põhjamaadele** | Töötaja | Tööandja | P2 | Sporditoetus | 2× | Sõeluuring + programm | K | Kõrge | €20k+ | 7 |
| 20 | **Kirurgi protokolli järgimise jälgija** (post-op rada) | Ortopeed | Haigla/kliinik | P6 | Puudub | 3× | Rada + teavitused | K | Madal | €10–30k | 6 |
| 21 | **Mitmekeelne patsiendijuhiste generaator** | Terapeut | Kliinik | P2 | Käsitsi/PDF | 4× | Plaan → juhised N keeles | M | Keskmine | +€1–2k | 2 |
| 22 | **Junior-terapeudi kliinilise arutluse treener (CPD)** | Noor terapeut | Kliinik/kool | P1 | Mentorlus | 2× | Juhtumisimulaator | M | Madal | €500–3k | 4 |
| 23 | **Kõnepõhine testide sisestamine hindamise ajal** ("käed on hõivatud") | Terapeut | Kliinik | P1,P4 | Kirjutamine pärast | 4× | Hääl → struktuur | M | Madal | Osa #1-st | 3 |
| 24 | **Kõnnaku analüüs ilma laborita** (ortopeedia, neuro) | Arst | Kliinik/haigla | P4 | Kõnnalabor või silmamõõt | 5× | Video + mudel | **K/S** | Keskmine | €10–40k | 7 |
| 25 | **Käe/randme/õla ROM ortopeedias** | Ortopeed | Haigla | P4 | Goniomeeter | 3× | Kaamera moodul | K | **Exer AI on sees** `[F]` | €10–40k | 7 |
| 26 | **Vaagnapõhja/naiste tervise rehabi platvorm** | Terapeut | Kliinik | P1,P2 | Alateenindatud | 2× | Vertikaalne rada | K | Madal (Sword sees) | €3–10k | 6 |
| 27 | **Kroonilise valu programmi adherentsuse coach** | Patsient | Kliinik/maksja | P2 | Grupiteraapia | 2× | Vestlus + jälgimine | K | Kõrge | €10k+ | 7 |
| 28 | **Kliiniku benchmarking / tulemusregister** (agregeeritud võrdlus) | Kliinikujuht | Kliinikukett | P4 | Puudub | 5× | Andmete agregeerimine | M | **Väga madal** | €5–20k | 6 |
| 29 | **Jõusaali/rehabi seadmete andmekiht** | Treener | Jõusaal | P2 | Puudub | 2× | Integratsioonid | M | Keskmine | €2–8k | 5 |
| 30 | **MSK kliiniliste uuringute andmekogumine** | Teadlane | Ülikool/ravimifirma | P4 | REDCap + käsitsi | 3× | eCRF + video | K | Madal | €20–100k | 6 |
| 31 | **Füsioteraapia praktika back-office agent** (arved, koodid, meeldetuletused) | Administraator | Kliinikuomanik | P1,P3 | Käsitsi | 3× | Agent + integratsioonid | M | Keskmine | €2–6k | 4 |
| 32 | **Sportlase "üks kaart" — kliiniku ja klubi vaheline jagatud rehabi-vaade** | Füsio mõlemal pool | Kliinik (mitte klubi) | P7 | WhatsApp | 3× | Jagatud episoodivaade | M | Madal | €2–8k | 6 |

## Ideed, mis tunduvad atraktiivsed, aga EI OLE head ärid (küsimus 6)

| Idee | Miks see tundub hea | Miks see tegelikult ei ole |
|---|---|---|
| **AI vigastusriski ennustus klubidele** | Tohutu valu (€3,45 mld/5a) `[F]`, selge ostja | Tõendusbaas puudub `[F]`; ostjaid on maailmas sadu; klubide staap vahetub → churn; ROI-d ei saa tõestada |
| **AI personaaltreener (B2C)** | Suur turg, lihtne demo | CAC > LTV; churn; Apple/Google/Strava on tasuta alternatiiv; maksevalmidus madal |
| **AI movement screening sportlastele** | Ilus demo, "prevention" narratiiv | Screening'u ennustusvaliidsus on tõestatult nõrk `[F]`; ostja ebaselge; mõõdik ilma tegevuseta |
| **Return-to-play readiness score** | Kõrge panus, klubid tahavad | Kriteeriumid ei ennusta korduvvigastust `[F]`; meditsiiniseadme klassifikatsioon; vastutus |
| **Koduharjutuste app adherentsusega** | Selge probleem (30–70% mitte-adherentsus) `[F]` | **Physitrack tõestab, et turg maksab vähe** `[F]`; adherentsus on käitumuslik probleem |
| **"Euroopa Hinge Health"** | Suur turg, tõestatud mudel | 5 aastat ja €200M+ hilja; Sword blokeerib EL-i; nõuab kliinikuvõrku |
| **AI diagnostika otse patsiendile** | Suur mõju | MDR IIa+; LLM-ide alatriaaži risk `[F]`; vastutus |
| **Whoop-laadne recovery riistvara** | Tarbijad ostavad | Riistvara marginaalid, Jawbone'i muster, kirjastatud skoorid valideerimata `[F]` |

---

# 12. TOP 10 võimalus — punktiskaala 1–10

Kasutan kogu skaalat. Skoorid on **minu hinnangud `[H]`** ptk 3–10 tõendite põhjal. `Reg. raskus` ja `Konkurents` ja `Distributsioon` on **pöördskaalal** (10 = lihtne/vähe), et kokkusumma oleks tõlgendatav.

| # | Idee | Prob. tõsidus | Prob. sagedus | WTP | Turu suurus | AI eelis | Teh. teostatavus | Reg. lihtsus | Konk. vähesus | Distr. lihtsus | Time-to-MVP | Data moat | Laienemine | ROI mõõdetavus | **Σ (130)** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **Rehab-native AI copilot** (scribe + episood + raportid) | 7 | 10 | 8 | 8 | 8 | 9 | 8 | 5 | 7 | 9 | 6 | 8 | 9 | **102** |
| 2 | **Spordimeditsiini episoodiplatvorm** (post-op/RTS rada) | 9 | 5 | 8 | 5 | 7 | 7 | 6 | 8 | 6 | 6 | 7 | 7 | 7 | **88** |
| 3 | **Kliiniku tulemuste ja benchmarkingu kiht** | 6 | 7 | 6 | 6 | 7 | 8 | 8 | 9 | 5 | 7 | **9** | 8 | 8 | **94** |
| 4 | **Dropout-riski ennustus + tagasikutse** | 6 | 9 | 7 | 6 | 5 | 9 | 9 | 7 | 8 | 9 | 4 | 5 | **10** | **94** |
| 5 | **Klubi/akadeemia meditsiiniline dokumentatsioon** | 6 | 8 | 5 | 4 | 6 | 8 | 8 | 7 | 6 | 8 | 6 | 5 | 5 | **82** |
| 6 | **Kaamerapõhine mõõtmiskiht kliinikule** | 6 | 7 | 6 | 7 | 8 | 6 | 5 | 5 | 6 | 5 | 8 | 8 | 6 | **83** |
| 7 | **Föderatsiooni vigastusregistri automatiseerimine** | 5 | 5 | 6 | 3 | 6 | 8 | 9 | **10** | 5 | 7 | 7 | 4 | 6 | **81** |
| 8 | **Maksja/tööandja aruandluse pakk** | 6 | 6 | 7 | 6 | 6 | 8 | 7 | 8 | 5 | 7 | 6 | 7 | 8 | **87** |
| 9 | **GPS/wearable andmete janitor klubidele** | 7 | 9 | 6 | 3 | 7 | 7 | 9 | 5 | 5 | 7 | 5 | 4 | 5 | **79** |
| 10 | **MSK-triaaž avalikule sektorile** | **10** | 8 | 8 | 9 | 7 | 5 | **2** | 5 | 2 | 3 | 8 | 8 | 6 | **81** |

## Kommentaarid pingerea kohta

- **#1 võidab mitte sellepärast, et probleem oleks kõige tõsisem (7/10), vaid sellepärast, et see on ainus, kus KÕIK praktilised teljed on korraga rohelised:** sagedus 10, teostatavus 9, time-to-MVP 9, ROI 9, regulatsioon 8. Selle nõrkus on konkurents (5) ja moat (6) — need on reaalsed riskid, mitte kosmeetika.
- **#10 (triaaž) on selle nimekirja kõige tähtsam probleem (10/10) ja kõige halvem startup.** Regulatiivne lihtsus 2, distributsioon 2, time-to-MVP 3. See on ettevõte, mida ehitab keegi, kellel on 10 aastat ja €50M — mitte esimene toode.
- **#9 (andmete janitor) on parim näide "huvitav tehnoloogia ≠ hea äri"**: probleem on igapäevane ja tõeline, aga turu suurus 3/10 tapab.
- **#3 on ainus, kus data moat on 9** — kui suudate agregeerida episoodi-tasemel tulemusi üle paljude kliinikute, siis see andmestik on kordumatu. **Aga see ei ole eraldi toode; see on #1 loomulik teine peatükk.**

---

# 13. Kontrariaanne otsing — alahinnatud võimalused

Nõue oli mitte keskenduda ilmsele. Siin on kohad, kus **suured firmad ei ole tugevalt sees** ja kus töö on igav, korduv ja tasustatav.

| Alahinnatud koht | Miks see on alahinnatud | Miks see on väärtuslik |
|---|---|---|
| **Vahetus visiitide vahel toimuv** | Ei ole demogeeniline | Seal toimub 95% ajast; dropout tekib seal (>20% vahelejätmist esimeses 4 nädalas → 3,5× katkestamise risk `[F]`) |
| **Väljakirjutamise dokument (discharge summary)** | Igav | Võtab 20–60 min, kordub iga episoodi lõpus, ja on ainus artefakt, mida saatja arst tegelikult loeb |
| **Maksja/tööandja aruandlus** | Administratiivne | Value-based lepingud tulevad; kes suudab tulemusi näidata, see saab lepingu |
| **Kliiniku läbilaskevõime** (kalendrite optimeerimine) | Ei ole "AI in healthcare" | Otsene tulu: iga täidetud slot = €50–80 |
| **Outcome measurement** | Kliinikud ei tee seda, sest see on tüütu (vastavus 29–42% `[F]`) | See on kogu tulevase väärtuse alus (moat, maksjad, tõendus) |
| **Sportlase ja välise kliiniku vaheline info** | "Kellegi teise probleem" | Kaks organisatsiooni, üks patsient, null jagatud süsteemi (P7) |
| **Programmeerimise (harjutuste määramise) automatiseerimine kliiniku enda mallide põhjal** | Näib triviaalne | Iga kliinik on aastaid ehitanud oma protokolle Wordis; nende digiteerimine on **switching cost'i allikas** |
| **Video + kliinilised märkmed KOOS** | Tehniliselt tüütu | Ainus koht, kus multimodaalne AI annab midagi, mida kumbki eraldi ei anna |
| **Väikesed nišid**: vaagnapõhi, käsi/randme rehab, laste ortopeedia, neuro-rehab | Liiga väike suurtele | Just õige suurus 3–5 inimesega tiimile |

**"Legora-like wedge" selles valdkonnas `[H]`:** keeruline professionaalne töövoog, kus AI eemaldab palju manuaalset tööd ja klient maksab = **füsioterapeudi episoodi dokumenteerimine + selle põhjal automaatselt tekkivad artefaktid** (harjutusplaan, progressiaruanne, väljakirjutamiskiri, maksja raport). See ei ole üks feature; see on **ahel, kus iga järgnev dokument tuleb tasuta, kui esimene on struktureeritud.** Just nagu juriidilises töös.

---

# 14. TOP 3 soovitust

## Soovitus 1 — Ehita füsioteraapia/spordimeditsiini kliiniku AI copilot (dokumentatsioon → struktuur → artefaktid)
Suurim kombinatsioon sagedusest, mõõdetavast ROI-st, madalast regulatiivsest riskist ja ostja=kasutaja dünaamikast. **Alusta Eestis, laiene Soome ja Rootsi.**

## Soovitus 2 — Ära ehita ühtegi toodet, mille põhilubadus on ennustus
Vigastusennustus, movement screening, RTP readiness score. Tõendus on vastu `[F]`, regulatsioon on karm, vastutus on kõrge ja ROI ei ole tõestatav. **Kui klient tahab seda, müü talle mõõtmist ja dokumenteerimist, mitte ennustust.**

## Soovitus 3 — Kui tahad kindlasti spordi juurde jääda, siis müü spordimeditsiini KLIINIKUTELE, mitte klubidele
Post-op ACL / õla / hüppeliigese rada, RTS-dokumentatsioon, sportlaspatsiendid. Sama töövoog nagu soovitus 1, aga kõrgema ACV ja tugevama diferentseerijaga. **Klubid tulevad hiljem kliinikute kaudu, mitte enne.**

---

# 15. Parim üksik idee

## **Rehab-native AI copilot füsioteraapia- ja spordimeditsiinikliinikutele**
### Töönimi: *episoodi-copilot* — "üks salvestus, kogu paberitöö"

### Probleem
Füsioterapeut töötab kätega. Ta ei saa seansi ajal kirjutada. Tulemus: dokumentatsioon tehakse pärast tööpäeva, halvasti ja hilja; objektiivsed mõõtmised jäävad kirja panemata; PROM-e ei koguta (vastavus 29–42% `[F]`); väljakirjutamiskiri ja progressiaruanne kirjutatakse käsitsi nullist; ja episoodi lõpus ei ole kellelgi struktureeritud ülevaadet sellest, mis 6 seansi jooksul juhtus. **Kogu see töö on juba tehtud — ta lihtsalt öeldi valjusti ja kadus.**

### Kasutaja
Füsioterapeut, spordifüsioterapeut, tegevusterapeut, spordiarst.

### Ostja
Kliiniku omanik / juht. **Väikeses ja keskmises kliinikus on ostja sageli ka kasutaja** — see on kogu ärimudeli tugevaim üksik omadus.

### Workflow (mida toode teeb)
1. Terapeut vajutab enne seanssi "salvesta" (või dikteerib 60 s pärast seanssi)
2. AI transkribeerib ja **struktureerib** → subjektiivne, objektiivne (sh testide arvväärtused, mis öeldi valjusti), hinnang, plaan
3. Terapeut **kinnitab või parandab** (30 s) → märge salvestub
4. Samast märkmest genereeritakse automaatselt: **harjutusplaani mustand** (kliiniku enda protokollidest), **patsiendi juhised** tema keeles, järgmise seansi eesmärgid
5. Episoodi jooksul koguneb **struktureeritud progress**; PROM-id küsitakse automaatselt õigel hetkel
6. Episoodi lõpus üks klõps → **väljakirjutamiskiri saatjale, progressiaruanne, ja (spordikontekstis) RTS-otsuse dokumentatsioon**, mis näitab, millised testid tehti, millal ja mis tulemustega

### AI
- Kõne→tekst (mitmekeelne: ET, FI, SV, EN — meditsiiniterminoloogia testimine on eraldi töö)
- LLM struktureerimiseks kliiniku enda skeemi (foundation model API, **oma mudelit ei ole vaja treenida**)
- Retrieval kliiniku enda protokollide/mallide üle
- **Ei mingit riskiennustust, ei mingit diagnoosi, ei mingit "valmis naasma" otsust MVP-s**

### Pricing / ärimudel
- **€89–149 / terapeut / kuu**, aastane leping, kliiniku miinimum 3 kohta
- Kliinik 8 terapeudiga = **~€10–14k ACV**
- Lisamoodulid hiljem: tulemuste aruandlus (€), benchmarking (€€), spordimeditsiini rada (€€)
- **ROI-argument müügis:** kui terapeut säästab 30 min päevas ja täidab sellega ühe lisaseansi (~€60), on tasuvus 1 seanss/nädalas. See on argument, mida kliinikuomanik kontrollib peast 10 sekundiga.

### Go-to-market
1. **Eesti: 10 pilootkliinikut**, sh 2–3 spordimeditsiini kliinikut, käsitsi müüdud, tasuta 60 päeva vastutasuks andmete ja intervjuude eest
2. Eesti Füsioterapeutide Liidu konverentsid, koolitused, ülikoolide (TÜ, TLÜ) füsioteraapia õppekavad
3. **Soome ja Rootsi**: erakliinikute ketid, kus ostuotsus on tsentraalne ja kliinikuid on kümneid — üks leping = 50–200 kohta
4. Partnerlus praktikahaldustarkvaraga (PMS), mitte konkureerimine sellega — **integratsioon on jaotuskanal**
5. Hiljem: Saksamaa (suurim EL turg, ~€30/seanss `[F]` tähendab mahupõhist mudelit → aja säästmine on veel väärtuslikum)

### Moat
Ausalt: **päev 1 moat on nõrk.** Moat ehitatakse kolmes kihis:
1. **Töövoo sügavus** (6–18 kuud): kliiniku enda protokollid, mallid, harjutusteek, integratsioonid → switching cost
2. **Episoodi-tasemel struktureeritud tulemusandmed** (12–36 kuud): see on **ainus koht valdkonnas, kus tekib andmestik, mida kellelgi teisel ei ole** — mitte "video sportlastest", vaid "mis tehti, mis mõõdeti, mis juhtus" tuhandete episoodide üle. Sellest sünnib benchmarking, ja hiljem tõenduspõhine sisend maksjatele.
3. **Regulatiivne positsioon** (24–48 kuud): kui hiljem on vaja MDR IIa, siis olete auditeeritavate andmete ja kvaliteedisüsteemiga juba pool teed

### Regulatiivne rada
- **Faas 1 (0–24 kuud): EI ole meditsiiniseade.** Dokumentatsioon ja töövoog, inimene kinnitab kõik. MDCG 2019-11 loogika toetab seda `[F]`. GDPR-i töötleja roll, EL hosting, DPA-d.
- **Faas 2 (24+ kuud):** kui lisandub otsust mõjutav funktsionaalsus (mõõtmine diagnostilise eesmärgiga, soovitused), siis MDR Rule 11 → tõenäoliselt IIa. AI Act'i kõrge riski kohustused Annex I toodetele jõustuvad 2028 `[F]` — ajastus töötab kasuks.

### Miks just nüüd
1. Kõnetuvastus ja LLM-id ületasid ~2024–2025 kvaliteedilävendi, mille alt struktureeritud kliiniline märge ei olnud võimalik ilma oma mudelita
2. **Turg on tõestanud, et selle eest makstakse** — Abridge $5,3B hinnang, Heidi $465M `[F]` — aga arstikeskselt
3. Inference'i hind on langenud tasemele, kus €100/kuu hinnastus jätab kõrge marginaali `[H]`
4. Regulatiivne aken on lahti kuni 2027–2028 `[F]`
5. Füsioterapeudid on valmis: 78% Itaalia füsioterapeutidest suhtub AI tulevasse kasutusse positiivselt, ja **kõige selgemini nimetatud kasu oli administratiivse koormuse vähendamine** `[F]`

### Miks incumbent pole seda juba lahendanud
- **Abridge/Nabla/Ambience** optimeerivad USA haiglat, arsti ja kodeerimist. Nende ostja on CIO, mitte 6-inimeseline kliinik Tartus. Nende toote loogika on **üks konsultatsioon = üks märge**; füsioteraapias on väärtus **episoodis üle 5–6 seansi**.
- **Physitrack/Medbridge** tulid harjutuste teegist ja on kinni selle ärimudeli hinnasurves (Physitracki tulu kahaneb `[F]`)
- **Praktikahaldustarkvara (PMS)** müüjad on aeglased ja nende R&D läheb arveldusse ja broneeringusse
- **Sword/Hinge** ehitavad **maksjale**, mitte kliinikule — kliinik on nende jaoks kulukoht, mitte klient
- Kõige lihtsam vastus: **see turg on liiga väike, et suurt firmat huvitada, ja liiga killustatud, et neid huvitaks Euroopa keeltes müüa.** See on täpselt õige suurus 3–6 inimesega tiimile.

---

# 16. Eesti → Euroopa strateegia

## Kas Eesti on hea beachhead? **Jah — aga ainult sellele ideele.**

### Miks Eesti töötab siin
| Eelis | Selgitus |
|---|---|
| **Ligipääs otsustajatele** | Kogu Eesti erafüsioteraapia sektor on läbikäidav 2–3 kuuga. 20 kliinikut = statistiliselt tähendusrikas valim |
| **Digitaalne baastase** | ~99% patsiendiandmetest digiteeritud, 200M+ dokumenti TIS-is, X-tee `[F]` → kliinikud ei karda digitaalset töövoogu |
| **Tervisekassa kui ainus ostja avalikul poolel** | Lihtsustab hilisemat aruandluse standardimist; üks partner, mitte 16 Bundesland'i |
| **Madal müügitakistus** | Otsustajad vastavad LinkedInis; konverentsid on väikesed ja tihedad |
| **Keeleline karm test** | Kui teie kõnetuvastus + struktureerimine töötab **eesti keeles**, siis soome, rootsi ja saksa keeles on see lihtsam. Eesti on hea "worst case" testkeskkond |
| **Kulubaas** | Tiim jääb odavamaks kui Berliinis või Londonis, mis pikendab runway'd |

### Miks Eesti üksi ei piisa
- Turu suurus: Eestis on **mõnisada kuni ~1500 praktiseerivat füsioterapeuti** `[S]` — täpne arv vajab kontrolli Terviseametist ja Eesti Füsioterapeutide Liidust. Isegi 100% turuosaga oleks ARR suurusjärgus €1–2M. **See on valideerimisturg, mitte lõppturg.**
- Maksevalmidus on madalam kui Põhjamaades

### Etapiviisiline plaan
| Faas | Aeg | Turg | Eesmärk |
|---|---|---|---|
| 0 | 0–3 kuud | Eesti, 10 kliinikut | Probleemi valideerimine, MVP, esimesed maksvad kliendid |
| 1 | 3–12 kuud | Eesti + Soome | €150–300k ARR; tõestatud ajasääst mõõdetuna, mitte küsitletuna |
| 2 | 12–24 kuud | Rootsi, Taani, Norra | €1M+ ARR; ketid, mitte üksikkliinikud |
| 3 | 24–48 kuud | Saksamaa, Holland, UK | Keelemoodulid + integratsioonid + tulemuste kiht |

### Mille jaoks Eesti EI ole hea beachhead `[H]`
- Kindlustus/maksja-mudel: Tervisekassa on ainus maksja ja tema müügitsükkel ei ole startupi-sõbralik
- Profisport: Eesti klubide eelarved on liiga väikesed, et tootehinda valideerida
- B2C: turg liiga väike CAC-mudelite testimiseks

---

# 17. Red Team — TOP 5 idee, iga kohta 10 tugevaimat ebaõnnestumise põhjust

TOP 5 punktisumma järgi: (1) Rehab copilot 102, (2) Tulemuste/benchmarkingu kiht 94, (3) Dropout-riski ennustus 94, (4) Spordimeditsiini episoodiplatvorm 88, (5) Maksja/tööandja aruandlus 87.

## R1. Rehab-native AI copilot

1. **Üldised scribe'id laienevad allapoole.** Abridge ($5,3B), Heidi, Nabla `[F]` lisavad allied health mallid ühe sprindiga. Nende hind võib minna nulli lähedale kui strateegiline liigutus.
2. **Praktikahaldustarkvara (PMS) lisab scribe'i sisseehitatud funktsioonina.** WebPT, Cliniko, Nordic PMS-id — kui see on nende paketis "tasuta", siis eraldi ostmiseks pole põhjust. See on kõige tõenäolisem surmapõhjus.
3. **Ajasääst ei realiseeru rahaks.** Terapeut säästab 30 min, aga kalender on nagunii täis või tühi — säästetud aeg ei muutu lisaseansiks. Siis on ROI "elukvaliteet", mille eest kliinikuomanik maksab vähem.
4. **Eesti/soome keele kvaliteet meditsiiniterminoloogias on halvem kui inglise keeles.** Kui märge vajab 3 min parandamist 8 min asemel, siis säästate 5 min, mitte 8 — väärtuspakkumine kahaneb.
5. **Salvestamine seansi ajal kohtab vastuseisu.** Patsiendi nõusolek, terapeudi ebamugavus ("ma räägin patsiendiga muul viisil kui dikteerin"), müra ravikabinetis, käsitsi ravi ajal vaikus.
6. **GDPR-i takistus on tegelik, mitte teoreetiline.** Kliinikud küsivad: kus andmed on, kas mudel treenib nendel, kes on alltöötleja. Iga vastus "USA" tapab tehingu Põhjamaades.
7. **Turg on liiga väike, et kasvada VC-tempoga.** Eesti + Põhjamaad füsioteraapias on realistlikult **€10–30M SAM** `[S]`; see on hea bootstrap-äri, aga võib olla liiga väike Series A-le.
8. **ACV on madal ja müük on ükshaaval.** €10k ACV nõuab 100 klienti €1M ARR-i jaoks. Ilma kettide või PMS-partnerluseta on see 3–4 aastat käsitsi müüki.
9. **Terapeutide usaldus võib olla madalam kui küsitlused näitavad.** 78% "positiivne suhtumine tulevasse kasutusse" `[F]` ei ole sama mis maksmine; ainult 50% pidas AI-vestlusroboteid kliiniliselt kasulikuks `[F]`.
10. **Hallutsinatsioon kliinilises märkmes on maineriskiga sündmus.** Üks juhtum, kus AI kirjutas märkmesse testi, mida ei tehtud, ja mis läks kohtusse või ajakirjandusse, võib väikese müüja Euroopa turul tappa.

**Verdikt pärast red-teami: JÄÄB ATRAKTIIVSEKS, aga kitsamalt kui alguses.** Kaks põhjust: (a) riskid #1, #2 ja #8 on tõelised ja määravad, kas see on €2M või €20M äri; (b) aga probleem ise on **tõestatult iga päev olemas ja ostja on kättesaadav**, mis on haruldane. **Tingimus: toode peab kiiresti liikuma "märkmest" "episoodi ja artefaktide" juurde** — pelgalt scribe on kaotatud lahing.

## R2. Tulemuste ja benchmarkingu kiht

1. **Andmeid ei tule, kui alusprodukt ei ole juba kasutuses.** See ei ole eraldi ettevõte; see on teine peatükk. Iseseisvana ehitatuna surete andmenäljas.
2. **Kliinikud ei taha võrdlust.** Benchmarking näitab, kes on halvem — see on ostja jaoks negatiivne stiimul.
3. **PROM-i vastavus on 29–42% `[F]`** — kui andmed on nii lünklikud, ei ole benchmark statistiliselt kaitstav.
4. **Case-mix'i korrigeerimine on raske.** Ilma selleta on iga võrdlus ebaõiglane ja kliiniliselt rünnatav.
5. **Maksjad ei pruugi seda osta EL-is**, kus value-based lepingud liiguvad aeglaselt.
6. **Andmete jagamise juriidika** (mitme vastutava töötleja agregeerimine) on GDPR-i all tüütu ja aeglane.
7. **Akadeemiline kriitika**: registrid ilma metodoloogilise range'useta saavad publitseerimisel pihta.
8. **Konkurents riiklikelt registritelt** (nt Skandinaavia kvaliteediregistrid), mis on tasuta.
9. **Väärtus realiseerub aastate pärast**, mis ei sobi startupi rahavooga.
10. **Moat on tegelikult võrgustikuefekt, mille käivitamine nõuab kriitilist massi**, mida €1M ARR-i juures ei ole.

**Verdikt: EI OLE iseseisev ettevõte. On tugev moat-kiht idee #1 peal.** Ärge alustage sellest.

## R3. Dropout-riski ennustus ja tagasikutse

1. **See on funktsioon, mitte toode.** Iga PMS võib selle lisada; ennustus kalendriandmetest ei ole tehniliselt raske.
2. **ROI on mõõdetav ja seetõttu ka ümberlükatav.** Kui A/B test näitab 3% paranemist, siis kliinik lõpetab.
3. **Ennustus ilma sekkumiseta on kasutu**, ja sekkumine (helistamine) nõuab **inimest**, kelle aega te ei säästa.
4. **Osa väljalangevusest on hea** (patsient paranes) — mudel karistab õiget käitumist.
5. **Väikestel kliinikutel ei ole piisavalt andmeid** oma mudeli treenimiseks; jagatud mudel toob GDPR-i probleemi.
6. **Konkurents üldistelt no-show lahendustelt** (Zocdoc-tüüpi, kalendritarkvara) on kõrge.
7. **ACV on väike** (€2–5k), müük on sama raske kui suurema toote puhul.
8. **Patsientide "spämmimise" risk** kahjustab kliiniku brändi.
9. **Ei loo andmeeelist** — kalendriandmed ei ole kordumatud.
10. **Käitumise muutmise tõendus on nõrk**: meeldetuletuste mõju on kirjanduses tagasihoidlik.

**Verdikt: EI OLE eraldi ettevõte. On hea müügiargument ja moodul idee #1 sees.**

## R4. Spordimeditsiini episoodiplatvorm (post-op / RTS rada)

1. **Kliiniline alusloogika on nõrgem, kui tundub.** RTS-kriteeriumide läbimine ei ole seotud madalama kordusvigastuse riskiga `[F]` — teie toote põhiväide on teaduslikult rünnatav.
2. **Regulatiivne piir on lähedal.** Kui toode ütleb midagi valmisoleku kohta, olete MDR Rule 11 all.
3. **Vastutus on kõrgeim kogu valdkonnas** — vale RTS-otsus võib lõpetada karjääri.
4. **Turu suurus on väike**: spordimeditsiini kliinikuid on Euroopas tuhandeid, mitte kümneid tuhandeid.
5. **Exer AI plaanib sports medicine mooduli 2026 lõpuks/2027 alguseks** `[F]`, Mayo Clinicu jaotusega — kiire konkurent tugeva usaldusväärsusega.
6. **Ortopeedid on aeglased ostjad** ja nende tarkvaraostud käivad haigla kaudu.
7. **Protokollid erinevad kliiniku ja kirurgi kaupa** → konfiguratsioonikoormus on suur, marginaal langeb.
8. **Post-op maht ühe kliiniku kohta on väike** (kümneid ACL-e aastas) → hind ei saa olla kõrge kasutuse pealt.
9. **Testiriistvara sõltuvus** (isokineetika, jõuplatvormid) piirab levikut kliinikutele, kellel see olemas on.
10. **Sportlane ei ole ostja** ja tema soov naasta töötab teie ettevaatliku toote vastu.

**Verdikt: ATRAKTIIVNE AINULT KUI ALAMSEGMENT idee #1 sees, mitte iseseisva tootena.** Kasutage seda kõrgema hinna ja diferentseerimise jaoks — ärge ehitage sellele ettevõtet.

## R5. Maksja / tööandja aruandluse pakk

1. **Ostja ei ole kliinik, vaid maksja** — müügitsükkel pikeneb 8 nädalalt 12 kuule.
2. **EL-i maksjad ei ole veel value-based** → nõudlus on ennatlik.
3. **Iga riik nõuab erinevat vormi** → tootest saab teenus.
4. **DiGA tee on kallis ja hinnasurve all**: käivitushinnad €200–700/3 kuud langevad läbirääkimistel ~50% (mediaan €221) `[F]`.
5. **Tööandjate MSK-programmide kasutusmäär on madal** — tööstuse andmetel sageli 2–4% `[V]`, mis nõrgestab kogu ROI-narratiivi.
6. **Sword ja Hinge on juba maksja laual** ja nende müügijõud on suurusjärgu võrra suurem.
7. **Tõendusnõue enne tulu** — maksja tahab RCT-d, mida startupil ei ole.
8. **Andmete kvaliteet sõltub kliinikutest**, keda te ei kontrolli.
9. **Poliitiline risk** (tervishoiu rahastuse muutused) võib tehingu ühe otsusega tühistada.
10. **Kliinikud võivad seda tajuda kontrollina**, mitte abina, ja blokeerida.

**Verdikt: EI OLE esimene toode.** On loomulik 3. peatükk, kui teil on juba andmed ja kliinikute võrgustik.

## Red-teami koondjäreldus `[H]`

Viiest ideest **jääb püsti üks: #1** — ja seegi tingimusel, et see ei jää scribe'iks. Ülejäänud neli on **moodulid või hilisemad peatükid sama ettevõtte sees**, mitte iseseisvad ettevõtted. See on tegelikult hea uudis: see tähendab, et **ideid ei ole viis, vaid üks, millel on selge 3-aastane laienemistee.**

---

# 18. Kill Criteria — millised faktid tähendaksid, et seda EI tohi ehitada

Need on **eelnevalt kokku lepitud lävendid**, mitte hilisemad ratsionaliseeringud.

| # | Kriteerium | Lävend | Kuidas mõõta |
|---|---|---|---|
| K1 | **Aeg ei ole tegelik probleem** | Kui <60% intervjueeritud terapeutidest ütleb dokumentatsiooni spontaanselt (ilma juhatamata) 3 suurima ajaraiskaja hulgas | 25 intervjuud, avatud küsimus enne teemast rääkimist |
| K2 | **Mõõdetud ajasääst on liiga väike** | Kui reaalne mõõdetud sääst on **<5 min/patsient** pärast parandamist | Ajastatud A/B: 20 seanssi tootega vs 20 ilma, sama terapeut |
| K3 | **Keelekvaliteet ei kanna** | Kui eestikeelse märkme parandamiseks kulub >50% ajast, mis kulunuks nullist kirjutamiseks | Struktureeritud test 50 salvestusega |
| K4 | **Maksevalmidus puudub** | Kui <30% pilootkliinikutest on nõus maksma €89/terapeut/kuu pärast tasuta perioodi | Tegelik makse, mitte "jah, ma maksaksin" |
| K5 | **PMS blokeerib** | Kui 2 suurimat piirkondlikku PMS-i teatavad, et lisavad sama funktsiooni 6 kuu jooksul **ja** keelduvad integratsioonist | Otsevestlused PMS-müüjatega |
| K6 | **Salvestamise vastuseis** | Kui >40% patsientidest keeldub salvestamise nõusolekust | Piloodi nõusolekumäär |
| K7 | **Ajasääst ei muutu väärtuseks** | Kui piloodi kliinikutes ei kasva ei seansside arv ega terapeudi rahulolu mõõdetavalt | Enne/pärast andmed 3 kuu jooksul |
| K8 | **Ohutusintsident** | Üks kliiniliselt oluline hallutsinatsioon, mis jõuab kinnitatud märkmesse ja mida kinnitusprotsess ei püüa | Logide auditeerimine |

**Kui K1, K2 või K4 kukub läbi → ideed ei tohi ehitada.** Ülejäänud on tõsised hoiatused, mis nõuavad toote või strateegia muutust.

---

# 19. Validation Plan — täpselt mida teha järgmise 30 päeva jooksul

**Eesmärk ei ole ehitada. Eesmärk on tappa idee 30 päevaga, kui see on tapetav.**

## Nädal 1 (päevad 1–7): probleemi olemasolu, mitte lahenduse huvi

- [ ] **Koosta nimekiri 40 Eesti kliinikust** (era-füsioteraapia + spordimeditsiin: Tartu, Tallinn, Pärnu). Allikad: Terviseameti tegevuslubade register, Eesti Füsioterapeutide Liit, Google Maps
- [ ] **Broneeri 20 intervjuud** (30 min). Sõnastus: "Uurin füsioterapeutide tööpäeva ülesehitust" — **mitte** "ehitan AI toodet"
- [ ] Vii läbi **vähemalt 12 intervjuud**. Küsimused rangelt selles järjekorras:
  1. Kirjelda eilne tööpäev tund tunni haaval
  2. Mis võttis rohkem aega, kui oleks pidanud?
  3. Mida sa teed pärast viimast patsienti?
  4. *(alles nüüd)* Kui palju aega läheb dokumentatsioonile? Millal sa selle teed?
  5. Mis juhtub, kui sa seda ei jõua?
  6. Mis on viimane tarkvara, mille eest sa oma rahaga maksid?
- [ ] **Kirjuta iga intervjuu järel üles verbatim tsitaadid**, mitte kokkuvõtted
- [ ] **Kontrolli kill criteria K1** päeva 7 lõpus

## Nädal 2 (päevad 8–14): tegelike numbrite mõõtmine

- [ ] **Palu 5 terapeudil mõõta 3 päeva jooksul tegelikku dokumentatsiooniaega** (lihtne vorm: patsient, algus, lõpp). See asendab vendorite väited päris andmetega — **see üksik samm eristab teid 90% asutajatest**
- [ ] **Küsi 5 kliinikult nende praegust dokumentatsiooni näidist** (anonümiseeritud) → mõistke, mis struktuur on tegelikult vaja
- [ ] **Räägi 3 kliinikuomanikuga eraldi ostjana**: mis on nende suurim kulukoht, mille eest nad sel aastal on tarkvara ostnud, kui palju maksid
- [ ] **Kaardista, mis PMS-i nad kasutavad** ja kas neil on API
- [ ] **Kontrolli kill criteria K2 esialgne signaal**

## Nädal 3 (päevad 15–21): tehniline reaalsustest

- [ ] **Ehita "Wizard of Oz" prototüüp** (mitte päris toode): salvesta 15 päris (nõusolekuga, anonümiseeritud) seanssi → jookseta olemasoleva kõnetuvastuse + LLM-i kaudu → tooda struktureeritud märge
- [ ] **Näita 5 terapeudile nende enda seansi märget** ja mõõda: mitu minutit kulub parandamiseks? Kas nad kasutaksid seda?
- [ ] **Testi eesti keele kvaliteet** meditsiiniterminoloogias eraldi (K3)
- [ ] **Küsi patsientide nõusolekumäära** salvestamiseks (K6)
- [ ] Räägi 2 PMS-müüjaga integratsioonist ja nende plaanidest (K5)

## Nädal 4 (päevad 22–30): maksevalmidus, mitte huvi

- [ ] **Küsi 8 kliinikult ettemaksu või allkirjastatud LOI-d** hinnaga €89/terapeut/kuu, algusega 60 päeva pärast. **Tasuta pilooti mitte pakkuda enne, kui hinnast on räägitud** — muidu ei mõõda te midagi
- [ ] Eesmärk: **vähemalt 3 kliinikut ütlevad jah rahaga või siduva kokkuleppega** (K4)
- [ ] **Räägi 2 Soome ja 1 Rootsi kliinikuketiga** — kas sama probleem on olemas, kas hinnatase kannab
- [ ] **Kirjuta 2-leheline otsusedokument**: mida kuulsite, mis kill criteria olek on, mis on otsus

## Mida NEED 30 päeva EI sisalda
- Toote ehitamist (välja arvatud Wizard of Oz)
- Ettevõtte asutamist
- Rahastuse otsimist
- Pitch deck'i
- **Vestlusi ühegi klubi ega sportlasega** — see on hilisem, mitte praegune küsimus

## Otsusereegel päeval 30
| Tulemus | Otsus |
|---|---|
| ≥3 maksvat/siduvat + mõõdetud sääst ≥8 min/patsient | **Ehita.** |
| 1–2 maksvat + sääst 5–8 min | **Pikenda valideerimist 30 päeva**, testi Soomes |
| 0 maksvat või sääst <5 min | **Ära ehita.** Vaata uuesti P3 (dropout) või P7 (info liikumine) |

---

# 20. Final Verdict

## Hinne: **7/10**

### Kuidas see hinne kujuneb
| Komponent | Hinne | Põhjendus |
|---|---|---|
| Probleemi olemasolu | 9 | Dokumentatsioon, väljalangevus, mõõtmine on tõestatult reaalsed |
| Ostja kättesaadavus | 8 | Ostja = kasutaja väikeses kliinikus, lühike tsükkel |
| Tehniline teostatavus | 9 | Foundation model'id piisavad, riistvara pole vaja |
| Regulatiivne olukord | 8 | Aken lahti kuni 2027–2028, mitte-meditsiiniseadme tee on selge |
| Konkurentsiline kaitse | 4 | **Nõrgim koht.** Scribe kommoditiseerub; moat tuleb ehitada, seda ei ole |
| Turu suurus | 6 | Piisav €10–30M ettevõtteks, kaheldav €100M+ jaoks Euroopas üksi |
| Tõendusbaas AI eelisele | 8 | Selle konkreetse ülesande puhul, erinevalt ennustusest |
| **Valdkond tervikuna** | **6,5** | Suur probleem, aga enamik ilmseid ideid on kas tõestatult mitte-toimivad või juba hõivatud |
| **Parim üksik idee** | **7** | Selge, teostatav, kitsas |

### Mida see hinne EI ütle
See ei ütle, et "turg kasvab". MSK-turg kasvab, aga see ei ole argument. See ütleb, et **selles valdkonnas on üks konkreetne, korduv, kallis ja praegu manuaalne töövoog, mille automatiseerimise eest on olemas ostja, kes on ka kasutaja, ja mille ROI-d saab kontrollida ühe nädalaga.** Kõik ülejäänu selles valdkonnas on kas teaduslikult nõrk, juba hõivatud või liiga väike.

### Kolm asja, mida ma kõige rohkem kardan `[H]`
1. Et praktikahaldustarkvara lisab scribe'i sisseehitatuna enne, kui te jõuate episoodi-tasemel sügavuseni
2. Et ajasääst ei konverteeru rahaks kliiniku P&L-is, ja ostja mõistab seda 6 kuu pärast
3. Et Euroopa turg on liiga killustatud, et jõuda €10M ARR-ini enne raha otsalõppemist

---

**Kui mul oleks piiratud raha ja ma peaksin täna AI × sport × rehab valdkonnas ühe ettevõtte ehitama, ehitaksin rehab-natiivse AI copiloti füsioteraapia- ja spordimeditsiinikliinikutele — mis muudab ühe salvestatud seansi automaatselt kliiniliseks märkmeks, harjutusplaaniks, progressiaruandeks ja väljakirjutamisdokumendiks — sest see on ainus koht kogu selles valdkonnas, kus probleem kordub iga päev, ROI on kliiniku omaniku jaoks ühe nädalaga kontrollitav, ostja ja kasutaja on sama inimene, regulatiivne koorem on madal, ja toote väärtus ei sõltu ennustusest, mida teadus ei toeta.**

---

# 21. Mida ma EI suutnud kinnitada (avatud lüngad)

Aus nimekiri sellest, kus tõendus on puudulik ja mida tuleb valideerimisel ise mõõta:

| Lünk | Miks see on oluline |
|---|---|
| **Füsioterapeutide dokumentatsiooniaeg Euroopas** — leidsin ainult tarnijate väiteid (8–15 min/kontakt, 30–50% tööpäevast) `[V]`, mitte retsenseeritud uuringut | See on kogu #1 idee ROI-arvutuse alus. **Mõõta ise nädalal 2** |
| **Eesti praktiseerivate füsioterapeutide täpne arv** | Määrab beachhead'i suuruse. Küsida Terviseametist ja Eesti Füsioterapeutide Liidust |
| **Sword Healthi ja VALD-i tegelikud tulunumbrid** | Erakäes; kolmandate osapoolte hinnangud ei ole auditeeritud |
| **Zone7 / Kitman Labs'i sõltumatu efektiivsuse tõendus** | Ei leidnud ühtegi sõltumatut kontrollrühmaga uuringut — see on iseenesest tulemus |
| **CV-põhise reaalajas tagasiside pikaajaline mõju** | RCT-d on olemas, aga väikesed ja kordamata |
| **Põhjamaade füsioteraapiakliinikute hinnatasemed ja tarkvarakulutused** | Määrab ACV. Küsida otse nädalal 4 |
| **Digital MSK programmide tegelik kasutusmäär tööandjatel** | Leidsin 2–4% väite tööstuse blogist `[V]`, mitte sõltumatust allikast |

---

# 22. Allikad

## Kliiniline tõendus — vigastusennustus ja sõelumine
- Machine learning methods in sport injury prediction and prevention: a systematic review — https://pubmed.ncbi.nlm.nih.gov/33855647/
- Machine learning approaches to injury risk prediction in sport: a scoping review with evidence synthesis — https://pmc.ncbi.nlm.nih.gov/articles/PMC12013557/
- The application of machine learning in the prediction of sports injuries: systematic review and meta-analysis — https://pmc.ncbi.nlm.nih.gov/articles/PMC13530161/
- Acute to chronic workload ratio (ACWR) for predicting sports injury risk: systematic review and meta-analysis — https://pmc.ncbi.nlm.nih.gov/articles/PMC12487117/
- The acute-chronic workload ratio-injury figure and its 'sweet spot' are flawed — https://www.researchgate.net/publication/333589357
- Reliability, Validity, and Injury Predictive Value of the Functional Movement Screen: A Systematic Review and Meta-analysis — https://journals.sagepub.com/doi/abs/10.1177/0363546516641937

## Kliiniline tõendus — ACL, return-to-sport
- Return-to-Sport Criteria After ACL Reconstruction Fail to Identify the Risk of Second ACL Injury — https://pubmed.ncbi.nlm.nih.gov/36638338/
- The Association Between Passing Return-to-Sport Criteria and Second ACL Injury Risk: Systematic Review With Meta-analysis (JOSPT) — https://www.jospt.org/doi/10.2519/jospt.2019.8190
- Better Safe Than Sorry? Time to Return to Sport After ACLR as a Risk Factor for Second ACL Injury (JOSPT) — https://www.jospt.org/doi/10.2519/jospt.2023.11977
- Young Athletes Who Return to Sport Before 9 Months After ACLR Have a Rate of New Injury 7 Times That of Those Who Delay — https://pubmed.ncbi.nlm.nih.gov/32005095/
- Persistent isokinetic knee flexion strength deficits at RTS are not associated with a second ACL injury — https://pmc.ncbi.nlm.nih.gov/articles/PMC12310091/

## Kliiniline tõendus — telerehab, adherentsus, CV
- Telerehabilitation for chronic knee pain vs in-person: PEAK non-inferiority RCT (Lancet) — https://www.thelancet.com/journals/lancet/article/PIIS0140-6736(23)02630-2/abstract
- Telerehabilitation vs face-to-face PT for degenerative meniscal tear: non-inferiority RCT — https://pmc.ncbi.nlm.nih.gov/articles/PMC12398105/
- Telerehabilitation after arthroscopic ACL reconstruction: non-inferiority RCT — https://pmc.ncbi.nlm.nih.gov/articles/PMC12729216/
- Effects of a Computer Vision–Based Exercise Application for People With Knee Osteoarthritis: RCT (JMIR) — https://pmc.ncbi.nlm.nih.gov/articles/PMC12088618/
- Effectiveness of an AI-based home exercise app for rotator cuff-related shoulder pain: RCT — https://pubmed.ncbi.nlm.nih.gov/42531919/
- Interventions for enhancing adherence with physiotherapy: systematic review — https://www.sciencedirect.com/science/article/abs/pii/S1356689X10000871
- Prognostic factors of adherence to home-based exercise therapy: systematic review and meta-analysis — https://www.frontiersin.org/journals/sports-and-active-living/articles/10.3389/fspor.2023.1035023/full

## Kliiniline tõendus — pose estimation, wearables
- Accuracy and Validity of 3D Markerless Motion Capture Compared to Marker-Based Systems: Systematic Review — https://pmc.ncbi.nlm.nih.gov/articles/PMC13306381/
- Reliability and validity of computer vision-based markerless human pose estimation for hip and knee ROM — https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11783685/
- Validation of nocturnal resting heart rate and HRV in consumer wearables (Physiological Reports) — https://physoc.onlinelibrary.wiley.com/doi/10.14814/phy2.70527
- Accuracy, Utility and Applicability of the WHOOP Wearable Monitoring Device: systematic review — https://www.medrxiv.org/content/10.1101/2024.01.04.24300784.full.pdf

## Kliiniline tõendus — LLM-id, otsusetugi, hoiakud
- Tests of large language models' medical competence for clinical decision support of musculoskeletal rehabilitation — https://pmc.ncbi.nlm.nih.gov/articles/PMC12929487/
- Prompt Framing Modulates Safety in Shoulder and Elbow Red-Flag Vignettes: A Large Language Model Study — https://doi.org/10.3390/diagnostics16101439
- Evaluation of Large Language Models in Generating Physical Exercise Rehabilitation Programs for MSK Disorders — https://doi.org/10.3390/healthcare14152389
- Knowledge, use and perceptions of AI Chatbots among Italian physiotherapists: cross-sectional survey — https://www.frontiersin.org/journals/digital-health/articles/10.3389/fdgth.2025.1671521/full
- Attitudes of physical therapists toward AI diagnostics: barriers, enablers, clinical implications — https://link.springer.com/article/10.1186/s12909-025-08361-7

## Töövoog, dropout, PROM-id
- Reasons for patient no-shows and drop-offs after initial evaluation in physical therapy outpatient care — https://www.sciencedirect.com/science/article/abs/pii/S2468781225000748
- Improving physiotherapy adherence: no-shows and drop-offs (Physiotutors research review) — https://www.physiotutors.com/research/improving-physiotherapy-adherence-uncovering-the-hidden-reasons-behind-no-shows-drop-offs/
- PROMs use during physical therapy practice and associated factors — https://www.sciencedirect.com/science/article/pii/S2468781223000292
- Physiotherapist and nurse perspectives on acceptability and timing of PROMs in clinical practice — https://pmc.ncbi.nlm.nih.gov/articles/PMC13242462/
- Value-based Healthcare: Making PROMs Work for Musculoskeletal Care — https://pmc.ncbi.nlm.nih.gov/articles/PMC12106216/
- Data collection and utilisation in sports physiotherapy practice: qualitative study of UK sport physiotherapists — https://pubmed.ncbi.nlm.nih.gov/41985246/

## Regulatsioon
- MDCG 2019-11 Guidance on Qualification and Classification of Software (Euroopa Komisjon) — https://health.ec.europa.eu/system/files/2020-09/md_mdcg_2019_11_guidance_en_0.pdf
- European Revision of Primary Software Guidance (MDCG 2019-11 Rev 1) — https://www.emergobyul.com/news/european-revision-primary-software-guidance-mdcg-2019-11-revision-1-small-changes-meaningful
- EU MDR Rule 11 Software Classification guide — https://punktum.net/insights/eu-mdr-rule-11-software-classification-guide/
- AI Act guidelines for medical device manufacturers under MDR — https://quickbirdmedical.com/en/ai-act-medical-devices-mdr/
- EU AI Act & Medical Devices: 2027–2028 deadlines (Digital Omnibus) — https://trustedtracemed.com/resources/eu-ai-act-mdr-2026.html

## Turg, ettevõtted, finantsid
- Hinge Health lifts 2026 outlook after strong Q1 — https://www.fiercehealthcare.com/digital-health/hinge-health-lifts-2026-outlook-after-strong-q1-expansion-new-conditions
- Hinge Health projects 2026 revenue to hit $732M — https://www.fiercehealthcare.com/digital-health/hinge-health-projects-2026-revenue-hit-732m-buoyed-strong-growth-investments-ai
- Hinge Health goes public (Healthcare Dive) — https://www.healthcaredive.com/news/hinge-health-goes-public-digital-health-IPO-signal/748931/
- Sword Health secures $40M at $4B valuation — https://hlth.com/insights/news/sword-health-secures-40m-funding-at-4b-valuation-launches-mental-health-platform-2025-06-18
- Sword Health buys Kaia Health in $285M deal — https://www.fiercehealthcare.com/ai-and-machine-learning/sword-health-buys-kaia-health-285m-deal-expand-its-footprint-us-germany
- Physitrack (STO:PTRK) financials — https://stockanalysis.com/quote/sto/PTRK/
- Catapult Sports company profile (PitchBook) — https://pitchbook.com/profiles/company/56236-96
- Teamworks acquires Smartabase and three other technologies — https://www.prnewswire.com/news-releases/teamworks-announces-four-acquisitions-and-a-compliance-roadmap-to-solidify-its-position-as-the-operating-system-for-sports-301718839.html
- Exer AI / Mayo Clinic deployment (MobiHealthNews) — https://www.mobihealthnews.com/news/exclusive-exer-ai-expands-partnership-mayo-clinic-clinical-deployment
- Exer Labs raises $6.5M — https://www.builtincolorado.com/articles/exer-labs-raises-6m-healthtech-ai
- Kemtai (Crunchbase) — https://www.crunchbase.com/organization/kemtai
- Sportlyzer (StartupBlink / Estonian World) — https://estonianworld.com/technology/startup-spotlight-sportlyzer/
- Abridge revenue and funding (Sacra) — https://sacra.com/c/abridge/
- AI Medical Scribe Fundraising Guide 2026 — https://startupfundraising.com/ai-medical-scribe-fundraising

## Turu suurus, kulud, süsteemi surve
- PHTI: Virtual MSK Solutions Health Technology Assessment (June 2024) — https://phti.org/wp-content/uploads/sites/3/2024/06/PHTI-Virtual-MSK-Solutions-Assessment-Report-v1.1.pdf
- EU-OSHA: Musculoskeletal disorders — https://osha.europa.eu/en/themes/musculoskeletal-disorders
- Musculoskeletal health, wealth and business, and wider societal impact (Eur J Public Health) — https://academic.oup.com/eurpub/article/32/5/831/6659118
- CSP: NHS waiting lists rise demonstrates need for graduate physio job guarantee — https://www.csp.org.uk/news/2025-08-14-nhs-waiting-lists-rise-demonstrates-need-graduate-physio-job-guarantee
- AHP MSK waiting times in NHS Scotland (Public Health Scotland) — https://publichealthscotland.scot/publications/allied-health-professionals-musculoskeletal-waiting-times-in-nhs-scotland/
- Howden Men's European Football Injury Index 2024/25 — https://www.howdengroupholdings.com/reports/mens-european-football-injury-index-202425
- Player injuries cost European clubs €3.45bn over past 5 years — https://www.insideworldfootball.com/2025/12/17/player-injuries-cost-european-clubs-e3-45bn-past-5-years-finds-howden-report/
- The three-year evolution of Germany's Digital Therapeutics (DiGA) reimbursement program (npj Digital Medicine) — https://www.nature.com/articles/s41746-024-01137-1
- GKV report on utilization and development of DiGA care in Germany — https://mtrconsult.com/news/gkv-report-utilization-and-development-digital-health-application-diga-care-germany
- Remote Therapeutic Monitoring codes under Medicare (APTA practice advisory) — https://www.apta.org/contentassets/95321a10e951408db650e2f19b96699f/apta-practice-advisory-rtm-codes032023.pdf
- e-Estonia digital healthcare — https://e-estonia.com/programme/digital-healthcare/
- Tervisekassa e-health products — https://tervisekassa.ee/en/organisation/e-health-products
- Estonian Association of Physiotherapists (World Physiotherapy) — https://world.physio/membership/estonia

## Tööstuse allikad (kasutatud AINULT probleemide avastamiseks, mitte tõendina)
- Physical therapy documentation burden / AI scribe vendor blogs (SPRY, PT Everywhere, Tandem Health) `[V]`
- HMDG Private Practice Barometer — UK clinic economics `[V]` — https://hmdg.co.uk/private-practice-barometer/physio-clinic-profit-margins-uk-2026/
- Zone7 case studies `[V]` — https://zone7.ai/case-studies/validation-study/validation-study-injury-risk-forecasting-with-zone7-ai/
- Second Door Health: digital MSK utilization rates `[V]`

---

*Raport koostatud avalike allikate põhjal. Kõik `[V]` märgistusega väited pärinevad ettevõtete või tööstuse enda materjalidest ja neid ei tohi käsitleda tõendina. Kõik `[H]` ja `[S]` on autori hinnangud, mitte faktid.*
