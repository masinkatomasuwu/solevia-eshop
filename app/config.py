# - konfigurace aplikace: nastavení spojení s databází a zabezpečení session

class Config:
    # - SECRET_KEY: tajný klíč sloužící k podepisování cookies a ochraně proti CSRF útokům
    # - v produkci by zde mělo být dlouhé náhodné heslo
    SECRET_KEY = '1234'

    # - SQLALCHEMY_DATABASE_URI: adresa pro připojení k databázovému serveru
    # - formát: protokol+ovladač://uživatel:heslo@hostitel/název_databáze
    # - mysql+pymysql: říká Flasku, že používáme MySQL a knihovnu PyMySQL jako ovladač
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://student20:spsnet@dbs.spskladno.cz/vyuka20'

    # - vypne sledování změn objektů (šetří paměť a zvyšuje výkon aplikace)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # - SQLALCHEMY_ENGINE_OPTIONS: pokročilé nastavení pro stabilitu připojení
    SQLALCHEMY_ENGINE_OPTIONS = {
        # - pool_recycle: po 280 sekundách připojení obnoví (předchází chybám "MySQL server has gone away")
        'pool_recycle': 280,
        # - pool_pre_ping: před každým dotazem zkontroluje, zda je spojení stále aktivní
        'pool_pre_ping': True
    }