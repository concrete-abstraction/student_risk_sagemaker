#%%
from student_risk import config
import saspy
import sys
from datetime import date

#%%
sas = saspy.SASsession()

sas.submit("""
%let dsn = census;

libname &dsn. odbc dsn=&dsn. schema=dbo;

proc sql;
    create table acad_calendar as
    select distinct
        *
        ,intnx('dtday', term_census_dt, 31, 'same') as adj_term_census_dt format=datetime22.3
        ,intnx('dtday', term_midterm_dt, 15, 'same') as adj_term_midterm_dt format=datetime22.3
    from &dsn..xw_term
    where acad_career = 'UGRD'
    order by term_code
;quit;

proc sql;
    create table adj_acad_calendar as
    select distinct
        *
        ,day(datepart(term_begin_dt)) as begin_day
        ,month(datepart(term_begin_dt)) as begin_month
        ,year(datepart(term_begin_dt)) as begin_year
        ,day(datepart(adj_term_census_dt)) as census_day
        ,month(datepart(adj_term_census_dt)) as census_month
        ,year(datepart(adj_term_census_dt)) as census_year
        ,day(datepart(adj_term_midterm_dt)) as midterm_day
        ,month(datepart(adj_term_midterm_dt)) as midterm_month
        ,year(datepart(adj_term_midterm_dt)) as midterm_year
        ,day(datepart(term_end_dt)) as end_day
        ,month(datepart(term_end_dt)) as end_month
        ,year(datepart(term_end_dt)) as end_year
    from acad_calendar
    order by term_code
;quit;

filename calendar \"Z:\\Nathan\\Models\\student_risk\\supplemental_files\\acad_calendar.csv\" encoding=\"utf-8\";

proc export data=adj_acad_calendar outfile=calendar dbms=csv replace;

proc sql;
    select min(term_type) into: term_type from &dsn..xw_term where term_year = year(today()) and month(datepart(term_begin_dt)) <= month(today()) and month(datepart(term_end_dt)) >= month(today()) and acad_career = 'UGRD'
;quit;
run;
""")

term_type = sas.symget('term_type')

sas.endsas()

#%%
class Logger(object):
    def __init__(self):
        self.terminal = sys.stdout
        self.log = open(f'Z:\\Nathan\\Models\\student_risk\\logs\\main\\log_{date.today()}.log', 'w')

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)  

    def flush(self):
        pass


sys.stdout = Logger()

#%%
if __name__ == '__main__':

    if term_type == 'SPR':

        try:
            exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\frsh\\spr\\sr_prod_spr_frsh_midterm.py').read())
        except config.DateError as mid_error:
            print(mid_error)
            config.mid_flag = True
        else:
            exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\tran\\spr\\sr_prod_spr_tran_midterm.py').read())

            try: 
                exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\frsh\\spr\\sr_prod_spr_frsh_midterm.py').read())
            except config.DataError as mid_snap_error:
                print(mid_snap_error)
            else:
                exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\tran\\spr\\sr_prod_spr_tran_midterm.py').read())

                try:
                    exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\frsh\\spr\\sr_prod_spr_frsh_census.py').read())
                except config.DateError as cen_error:
                    print(cen_error)
                    config.cen_flag = True
                else:
                    exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\tran\\spr\\sr_prod_spr_tran_census.py').read())
            
                    try: 
                        exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\frsh\\spr\\sr_prod_spr_frsh_census.py').read())
                    except config.DataError as cen_snap_error:
                        print(cen_snap_error)
                    else:
                        exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\tran\\spr\\sr_prod_spr_tran_census.py').read())

                        try:
                            exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\frsh\\spr\\sr_prod_spr_frsh_eot.py').read())
                        except config.DateError as pre_error:
                            print(pre_error)
                            config.pre_flag = True
                        else:
                            exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\tran\\spr\\sr_prod_spr_tran_eot.py').read())

                            try: 
                                exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\frsh\\spr\\sr_prod_spr_frsh_eot.py').read())
                            except config.DataError as pre_snap_error:
                                print(pre_snap_error)
                            else:
                                exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\tran\\spr\\sr_prod_spr_tran_eot.py').read())

    if term_type != 'SPR':

        try:
            exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\frsh\\fal\\sr_prod_fal_frsh_midterm.py').read())
        except config.DateError as mid_error:
            print(mid_error)
            config.mid_flag = True
        else:
            exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\tran\\fal\\sr_prod_fal_tran_midterm.py').read())

            try: 
                exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\frsh\\fal\\sr_prod_fal_frsh_midterm.py').read())
            except config.DataError as mid_snap_error:
                print(mid_snap_error)
            else:
                exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\tran\\fal\\sr_prod_fal_tran_midterm.py').read())

                try:
                    exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\frsh\\fal\\sr_prod_fal_frsh_census.py').read())
                except config.DateError as cen_error:
                    print(cen_error)
                    config.cen_flag = True
                else:
                    exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\tran\\fal\\sr_prod_fal_tran_census.py').read())

                    try: 
                        exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\frsh\\fal\\sr_prod_fal_frsh_census.py').read())
                    except config.DataError as cen_snap_error:
                        print(cen_snap_error)
                    else:
                        exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\tran\\fal\\sr_prod_fal_tran_census.py').read())

                        try:
                            exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\frsh\\fal\\sr_prod_fal_frsh_admissions.py').read())
                        except config.DateError as adm_error:
                            print(adm_error)
                        else:
                            exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\tran\\fal\\sr_prod_fal_tran_admissions.py').read())
