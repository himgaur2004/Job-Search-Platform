"""
ingest_massive_user_csv.py — High-scale ingestion and ATS auto-discovery of hundreds of Indian startups from user CSV.
"""

import logging
import os
import re
import sys
from urllib.parse import urlparse

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.db import get_conn

logger = logging.getLogger(__name__)

# User provided raw CSV text snippet
RAW_CSV_DATA = """company_name,website_url,primary_sector,headquarters_city,funding_stage
CollegeDekho,https://www.collegedekho.in,E-learning,Bengaluru,Series B
BOX8,https://www.box8.in,Food & Beverages,Bengaluru,Growth Stage
Simpl,https://www.simpl.in,Consumer Services,Bengaluru,Series B
8i Ventures,https://www.8iventures.in,Venture Capital & Private Equity,Bengaluru,Growth Stage
PayGlocal,https://www.payglocal.in,Financial Services,Bengaluru,Series A
Curefit,https://www.curefit.in,"Health, Wellness & Fitness",Bengaluru,Growth Stage
Pocket FM,https://www.pocketfm.in,OTT,Bengaluru,Series B
CHARGE+ZONE,https://www.chargezone.in,Automotive,Bengaluru,Growth Stage
PlanetSpark,https://www.planetspark.in,Education Management,Bengaluru,Series B
LenDenClub,https://www.lendenclub.in,Financial Services,Bengaluru,Series A
CometChat,https://www.cometchat.in,Computer Software,Bengaluru,Series A
AgroStar,https://www.agrostar.in,AgriTech,Bengaluru,Series D
Bizongo,https://www.bizongo.in,Information Technology & Services,Bengaluru,Series D
Probus Insurance,https://www.probusinsurance.in,Insurance,Bengaluru,Growth Stage
MoEngage,https://www.moengage.in,Software Startup,Bengaluru,Series D
CloudSEK,https://www.cloudsek.in,Computer & Network Security,Bengaluru,Series A
Exponent Energy,https://www.exponentenergy.in,Automotive,Bengaluru,Pre-series A
Trinkerr,https://www.trinkerr.in,Capital Markets,Bengaluru,Series A
Zorro,https://www.zorro.in,Social network,Bengaluru,Seed
Ultraviolette,https://www.ultraviolette.in,Automotive,Bengaluru,Series C
NephroPlus,https://www.nephroplus.in,Hospital & Health Care,Bengaluru,Series E
Unremot,https://www.unremot.in,Information Technology & Services,Bengaluru,Seed
FanAnywhere,https://www.fananywhere.in,Financial Services,Bengaluru,Seed
PingoLearn,https://www.pingolearn.in,E-learning,Bengaluru,Growth Stage
Spry,https://www.spry.in,Music,Bengaluru,Seed
Enmovil,https://www.enmovil.in,Information Technology & Services,Bengaluru,Pre-series A
ASQI Advisors,https://www.asqiadvisors.in,Financial Services,Bengaluru,Pre-series A
Insurance Samadhan,https://www.insurancesamadhan.in,Insurance,Bengaluru,Pre-series A
Evenflow Brands,https://www.evenflowbrands.in,Consumer Goods,Bengaluru,Growth Stage
MasterChow,https://www.masterchow.in,Hauz Khas,Bengaluru,Seed
Fullife Healthcare,https://www.fullifehealthcare.in,Primary Business is Development and Manufacturing of Novel Healthcare Products in Effervescent forms using imported propriety ingredients.,Bengaluru,Growth Stage
MoEVing,https://www.moeving.in,MoEVing is India's only Electric Mobility focused Technology Platform with a vision to accelerate EV adoption in India.,Bengaluru,Growth Stage
Pristyn Care,https://www.pristyncare.in,Hospital & Health Care,Bengaluru,Series E
Plix,https://www.plix.in,"Health, Wellness & Fitness",Bengaluru,Series A
Uni Cards,https://www.unicards.in,Financial Services,Bengaluru,Series A
Practically,https://www.practically.in,E-learning,Bengaluru,Growth Stage
Nestasia,https://www.nestasia.in,Retail,Bengaluru,Series A
Vedic Cosmeceuticals,https://www.vediccosmeceuticals.in,Cosmetics,Bengaluru,Series A
Juspay,https://www.juspay.in,FinTech,Bengaluru,Series C
TranZact,https://www.tranzact.in,Information Technology & Services,Bengaluru,Series A
Atomberg,https://www.atomberg.in,Consumer Electronics,Bengaluru,Growth Stage
Ola,https://www.ola.in,Mobility,Bengaluru,Growth Stage
Mohalla Tech,https://www.mohallatech.in,Social media,Bengaluru,Series G
Stack,https://www.stack.in,Financial Services,Bengaluru,Seed
PropReturns,https://www.propreturns.in,Real Estate,Bengaluru,Growth Stage
WeSkill,https://www.weskill.in,E-learning,Bengaluru,Pre-seed
Fitpage,https://www.fitpage.in,"Health, Wellness & Fitness",Bengaluru,Growth Stage
ShopMyLooks,https://www.shopmylooks.in,Digital platform,Bengaluru,Growth Stage
ByteLearn,https://www.bytelearn.in,E-learning,Bengaluru,Seed
Dista,https://www.dista.in,Computer Software,Bengaluru,Seed
OfBusiness,https://www.ofbusiness.in,Financial Services,Bengaluru,Growth Stage
FRND,https://www.frnd.in,Online Media,Bengaluru,Series A
Metadome,https://www.metadome.in,Computer Software,Bengaluru,Pre-series A
Keka HR,https://www.kekahr.in,Information Technology & Services,Bengaluru,Growth Stage
Flo Mobility,https://www.flomobility.in,Industrial Automation,Bengaluru,Growth Stage
Yodacart,https://www.yodacart.in,E-commerce,Bengaluru,Pre-seed
TheHouseMonk,https://www.thehousemonk.in,Real Estate,Bengaluru,Growth Stage
Zepto,https://www.zepto.in,E-commerce,Bengaluru,Growth Stage
Sirona Hygiene,https://www.sironahygiene.in,"Health, Wellness & Fitness",Bengaluru,Growth Stage
Jumbotail,https://www.jumbotail.in,B2B Ecommerce,Bengaluru,Series C
Captain Fresh,https://www.captainfresh.in,Logistics & Supply Chain,Bengaluru,Series B
Deciwood,https://www.deciwood.in,Consumer Electronics,Bengaluru,Growth Stage
Kohbee,https://www.kohbee.in,E-learning,Bengaluru,Pre-seed
Perfora,https://www.perfora.in,Consumer Goods,Bengaluru,Pre-seed
Unbox Robotics,https://www.unboxrobotics.in,Logistics & Supply Chain,Bengaluru,Series A
Ninety One,https://www.ninetyone.in,Consumer Goods,Bengaluru,Series A
Gobillion,https://www.gobillion.in,Social commerce,Bengaluru,Seed
RIPPLR,https://www.ripplr.in,Logistics & Supply Chain,Bengaluru,Pre-series B
SK Finance,https://www.skfinance.in,Financial Services,Bengaluru,Series F
Eggoz,https://www.eggoz.in,Food & Beverages,Bengaluru,Series A
Fabriclore,https://www.fabriclore.in,Apparel & Fashion,Bengaluru,Pre-series A
Veefin,https://www.veefin.in,Information Technology & Services,Bengaluru,Growth Stage
Verandah,https://www.verandah.in,Apparel & Fashion,Bengaluru,Seed
Fi,https://www.fi.in,Financial Services,Bengaluru,Series B
Kiko Live,https://www.kikolive.in,Commerce,Bengaluru,Pre-series A
TurboHire,https://www.turbohire.in,Computer Software,Bengaluru,Growth Stage
The Hosteller,https://www.thehosteller.in,Hospitality,Bengaluru,Pre-series A
SatSure,https://www.satsure.in,Defense & Space,Bengaluru,Growth Stage
Ruptok Fintech,https://www.ruptokfintech.in,Financial Services,Bengaluru,Pre-series A
VilCart,https://www.vilcart.in,Retail,Bengaluru,Growth Stage
Dogsee Chew,https://www.dogseechew.in,Food & Beverages,Bengaluru,Pre-series A
Advantage Club,https://www.advantageclub.in,HR Tech,Bengaluru,Pre-series A
TRDR,https://www.trdr.in,Financial Services,Bengaluru,Growth Stage
Zoomcar,https://www.zoomcar.in,Mobility,Bengaluru,Growth Stage
Leap India,https://www.leapindia.in,Logistics & Supply Chain,Bengaluru,Growth Stage
SuperBottoms,https://www.superbottoms.in,Consumer Goods,Bengaluru,Growth Stage
Cora Health,https://www.corahealth.in,"Health, Wellness & Fitness",Bengaluru,Seed
Battery Smart,https://www.batterysmart.in,Renewables & Environment,Bengaluru,Pre-series A
The Good Glamm Group,https://www.thegoodglammgroup.in,Information Technology & Services,Bengaluru,Series D
Mosaic Wellness,https://www.mosaicwellness.in,"Health, Wellness & Fitness",Bengaluru,Series A
CloudFiles,https://www.cloudfiles.in,SaaS startup,Bengaluru,Pre-seed
The Viral Fever,https://www.theviralfever.in,Entertainment,Bengaluru,Growth Stage
Xpand,https://www.xpand.in,Retail,Bengaluru,Pre-series A
Troo Good,https://www.troogood.in,E-commerce,Bengaluru,Series A
Prodo,https://www.prodo.in,Business Supplies & Equipment,Bengaluru,Pre-seed
Unnati,https://www.unnati.in,FinTech,Bengaluru,Series A
Lysto,https://www.lysto.in,NFT,Bengaluru,Seed
Wakefit,https://www.wakefit.in,Furniture,Bengaluru,Series C
Buyofuel,https://www.buyofuel.in,Oil & Energy,Bengaluru,Seed
ElectricPe,https://www.electricpe.in,EV,Bengaluru,Seed
Vayana Network,https://www.vayananetwork.in,Financial Services,Bengaluru,Series C
Valuationary,https://www.valuationary.in,E-learning,Bengaluru,Pre-seed
Knocksense,https://www.knocksense.in,Online Media,Bengaluru,Growth Stage
Petpooja,https://www.petpooja.in,Information Technology & Services,Bengaluru,Growth Stage
Wingreens Farms,https://www.wingreensfarms.in,Food & Beverages,Bengaluru,Growth Stage
Doola,https://www.doola.in,Company-as-a-Service,Bengaluru,Growth Stage
EyeMyEye,https://www.eyemyeye.in,Eyewear,Bengaluru,Pre-series A
Bombay Hemp Company,https://www.bombayhempcompany.in,Textiles,Bengaluru,Growth Stage
DGV,https://www.dgv.in,Information Technology & Services,Bengaluru,Pre-series A
GuardianLink,https://www.guardianlink.in,Information Technology & Services,Bengaluru,Series A
Clinikk,https://www.clinikk.in,Hospital & Health Care,Bengaluru,Pre-series A
Toplyne,https://www.toplyne.in,Computer Software,Bengaluru,Growth Stage
Mensa,https://www.mensa.in,D2C,Bengaluru,Series B
GENLEAP,https://www.genleap.in,Professional Training & Coaching,Bengaluru,Seed
Planys,https://www.planys.in,Maritime,Bengaluru,Pre-series A
Wonderchef,https://www.wonderchef.in,Consumer Goods,Bengaluru,Growth Stage
GoKwik,https://www.gokwik.in,Information Technology & Services,Bengaluru,Series A
Velocity,https://www.velocity.in,Financial Services,Bengaluru,Series A
SalaryBox,https://www.salarybox.in,Financial Services,Bengaluru,Seed
Boingg,https://www.boingg.in,Furniture,Bengaluru,Seed
Better Capital,https://www.bettercapital.in,Venture Capital & Private Equity,Bengaluru,Growth Stage
Tickertape,https://www.tickertape.in,Financial Services,Bengaluru,Growth Stage
Zenpay Solutions,https://www.zenpaysolutions.in,Financial Services,Bengaluru,Growth Stage
Disprz,https://www.disprz.in,E-learning,Bengaluru,Series B
Arbo Works,https://www.arboworks.in,Computer Software,Bengaluru,Growth Stage
Inzpira,https://www.inzpira.in,E-learning,Bengaluru,Seed
Defy,https://www.defy.in,Financial Services,Bengaluru,Growth Stage
Mindhouse,https://www.mindhouse.in,"Health, Wellness & Fitness",Bengaluru,Seed
Homversity,https://www.homversity.in,Housing Marketplace,Bengaluru,Growth Stage
Toppersnotes,https://www.toppersnotes.in,Education Management,Bengaluru,Seed
NoBroker.com,https://www.nobrokercom.in,Real Estate,Bengaluru,Series E
Haber,https://www.haber.in,Industrial Automation,Bengaluru,Series B
True Balance,https://www.truebalance.in,Financial Services,Bengaluru,Growth Stage
Recordent,https://www.recordent.in,Financial Services,Bengaluru,Growth Stage
Koparo,https://www.koparo.in,Consumer Goods,Bengaluru,Seed
Indifi,https://www.indifi.in,Financial Services,Bengaluru,Growth Stage
Settl,https://www.settl.in,Real Estate,Bengaluru,Seed
Park+,https://www.park.in,Tech startup,Bengaluru,Series B
Simple Energy,https://www.simpleenergy.in,Automotive,Bengaluru,Pre-series
Dream Sports,https://www.dreamsports.in,Sports,Bengaluru,Growth Stage
Spinny,https://www.spinny.in,Automotive,Bengaluru,Series E
Rentomojo,https://www.rentomojo.in,Furniture Rental,Bengaluru,Growth Stage
Slice,https://www.slice.in,Financial Services,Bengaluru,Series B
21K School,https://www.21kschool.in,E-learning,Bengaluru,Pre-series A
Adda247,https://www.adda247.in,E-learning,Bengaluru,Series B
Loop Health,https://www.loophealth.in,Hospital & Health Care,Bengaluru,Growth Stage
Rupifi,https://www.rupifi.in,Financial Services,Bengaluru,Debt
RENEE Cosmetics,https://www.reneecosmetics.in,Cosmetics,Bengaluru,Pre-series A
Svish,https://www.svish.in,Consumer Goods,Bengaluru,Seed
Progcap,https://www.progcap.in,FinTech,Bengaluru,Series C
Smartstaff,https://www.smartstaff.in,Recruitment,Bengaluru,Growth Stage
BYJU'S,https://www.byjus.in,EdTech,Bengaluru,Growth Stage
Licious,https://www.licious.in,Food & Beverages,Bengaluru,Series G
Chalo,https://www.chalo.in,Mobility,Bengaluru,Series C
CoinSwitch Kuber,https://www.coinswitchkuber.in,Crypto,Bengaluru,Series C
LeadSquared,https://www.leadsquared.in,Computer Software,Bengaluru,Growth Stage
Rebel Foods,https://www.rebelfoods.in,Cloud kitchen,Bengaluru,Series F
Chingari,https://www.chingari.in,Entertainment,Bengaluru,Growth Stage
Ola Electric,https://www.olaelectric.in,Automotive,Bengaluru,Growth Stage
Zetwerk,https://www.zetwerk.in,Mechanical Or Industrial Engineering,Bengaluru,Growth Stage
Hubilo,https://www.hubilo.in,Software Startup,Bengaluru,Series B
M2P Fintech,https://www.m2pfintech.in,Financial Services,Bengaluru,Series C
CarDekho,https://www.cardekho.in,Automotive,Bengaluru,Series E
CRED,https://www.cred.in,Finance,Bengaluru,Series E
Groww,https://www.groww.in,Finance,Bengaluru,Series E
BharatPe,https://www.bharatpe.in,Financial Services,Bengaluru,Growth Stage
Teachmint,https://www.teachmint.in,E-learning,Bengaluru,Series B
Porter,https://www.porter.in,Logistics & Supply Chain,Bengaluru,Series E
DeHaat,https://www.dehaat.in,Information Technology & Services,Bengaluru,Series D
Acko,https://www.acko.in,Insurance,Bengaluru,Series D
Purplle,https://www.purplle.in,E-commerce,Bengaluru,Growth Stage
Vedantu,https://www.vedantu.in,E-learning,Bengaluru,Series E
Exotel,https://www.exotel.in,Telecommunications,Bengaluru,Series C
Meesho,https://www.meesho.in,Social commerce,Bengaluru,Growth Stage
Delhivery,https://www.delhivery.in,Logistics & Supply Chain,Bengaluru,Growth Stage
Postman,https://www.postman.in,Computer software,Bengaluru,Series D
OYO,https://www.oyo.in,Hospitality,Bengaluru,Series F2
Rapido,https://www.rapido.in,Information Technology & Services,Bengaluru,Growth Stage
Unacademy,https://www.unacademy.in,EdTech,Bengaluru,Growth Stage
upGrad,https://www.upgrad.in,EdTech,Bengaluru,Growth Stage
Jupiter,https://www.jupiter.in,Banking,Bengaluru,Series B
Fashinza,https://www.fashinza.in,Apparel & Fashion,Bengaluru,Series A
Urban Company,https://www.urbancompany.in,Home services,Bengaluru,Series F
BrowserStack,https://www.browserstack.in,SaaS startup,Bengaluru,Series B
KreditBee,https://www.kreditbee.in,FinTech,Bengaluru,Growth Stage
Cashfree,https://www.cashfree.in,FinTech,Bengaluru,Growth Stage
Refyne,https://www.refyne.in,FinTech,Bengaluru,Series A
Fampay,https://www.fampay.in,FinTech,Bengaluru,Series A
Khatabook,https://www.khatabook.in,Financial Services,Bengaluru,Series C
Smallcase,https://www.smallcase.in,FinTech,Bengaluru,Series C
MPL,https://www.mpl.in,Sports,Bengaluru,Series E
Apna,https://www.apna.in,Recruitment,Bengaluru,Series C
Pine Labs,https://www.pinelabs.in,Information Technology & Services,Bengaluru,Growth Stage
Jar,https://www.jar.in,FinTech,Bengaluru,Pre-series A
Dukaan,https://www.dukaan.in,Retail,Bengaluru,Series A
Leap Finance,https://www.leapfinance.in,Financial Services,Bengaluru,Series C
Curefoods,https://www.curefoods.in,Food & Beverages,Bengaluru,Growth Stage
Shiprocket,https://www.shiprocket.in,Logistics,Bengaluru,Series D1
Mamaearth,https://www.mamaearth.in,Healthcare,Bengaluru,Growth Stage
BlackBuck,https://www.blackbuck.in,Logistics & Supply Chain,Bengaluru,Series E
HealthifyMe,https://www.healthifyme.in,Healthcare,Bengaluru,Series C
Inshorts,https://www.inshorts.in,Internet,Bengaluru,Growth Stage
Pratilipi,https://www.pratilipi.in,Online storytelling,Bengaluru,Growth Stage
WinZO,https://www.winzo.in,Gaming,Bengaluru,Series C
Furlenco,https://www.furlenco.in,Consumer Goods,Bengaluru,Growth Stage
Leena AI,https://www.leenaai.in,Computer Software,Bengaluru,Series B
CARS24,https://www.cars24.in,Automotive,Bengaluru,Series F
ZestMoney,https://www.zestmoney.in,Financial Services,Bengaluru,Series C
FrontRow,https://www.frontrow.in,E-learning,Bengaluru,Series A
Leverage Edu,https://www.leverageedu.in,Higher Education,Bengaluru,Growth Stage
BetterPlace,https://www.betterplace.in,Information Technology & Services,Bengaluru,Series C
Eupheus Learning,https://www.eupheuslearning.in,E-learning,Bengaluru,Series C
"""


def parse_and_ingest():
    lines = RAW_CSV_DATA.strip().split("\n")
    if not lines:
        return

    header = lines[0]
    entries = []

    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) >= 2:
            name = parts[0].strip()
            url = parts[1].strip()
            sector = parts[2].strip() if len(parts) > 2 else "Technology"

            parsed = urlparse(url)
            domain = parsed.netloc.replace("www.", "") if parsed.netloc else url.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]

            career_url = f"https://www.{domain}/careers"
            entries.append((name, domain, career_url, sector))

    print(f"Parsed {len(entries)} company entries from CSV!")

    inserted_custom = 0
    with get_conn() as conn:
        for name, domain, career_url, sector in entries:
            try:
                conn.execute(
                    """
                    INSERT INTO companies_custom (name, domain, career_url, status)
                    VALUES (?, ?, ?, 'active')
                    ON CONFLICT(domain) DO UPDATE SET
                        career_url=excluded.career_url,
                        status='active'
                    """,
                    (name, domain, career_url)
                )
                inserted_custom += 1
            except Exception as e:
                logger.debug(f"DB error for {name}: {e}")
        conn.commit()

    print(f"Successfully ingested {inserted_custom} companies into companies_custom table!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parse_and_ingest()
