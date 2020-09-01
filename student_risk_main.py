import saspy
import sys
from datetime import date

#%%
sas = saspy.SASsession()

sas.submit("""%let dsn = census;

libname &dsn. odbc dsn=&dsn. schema=dbo;

proc sql;
    create table acad_calendar as
    select distinct
        *
        ,day(term_begin_dt) as begin_day
        ,month(term_begin_dt) as begin_month
        ,year(term_begin_dt) as begin_year
        ,day(term_census_dt) as census_day
        ,month(term_census_dt) as census_month
        ,year(term_census_dt) as census_year
        ,day(term_end_dt) as end_day
        ,month(term_end_dt) as end_month
        ,year(term_end_dt) as end_year
    from &dsn..xw_term
    where acad_career = 'UGRD'
    order by term_code
;quit;

filename calendar \"Z:\\Nathan\\Models\\student_risk\\Supplemental Files\\acad_calendar.csv\" encoding=\"utf-8\";

proc export data=acad_calendar outfile=calendar dbms=csv replace;
run;
""")

sas.endsas()

#%%
class Logger(object):
    def __init__(self):
        self.terminal = sys.stdout
        self.log = open(f'Z:\\Nathan\\Models\\student_risk\\Logs\\main\\log_{date.today()}.log', 'w')

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)  

    def flush(self):
        pass


sys.stdout = Logger()

# %%
if __name__ == '__main__':
    try:
        exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk_prod_census.py').read())
    except Exception as cen_error:
        print(cen_error)

    try:
        exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk_prod_admissions.py').read())
    except Exception as adm_error:
        print(adm_error)
