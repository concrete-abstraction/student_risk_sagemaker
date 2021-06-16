#%%
from student_risk import config
import saspy
import sys
import time
import traceback
from datetime import date

#%%
start = time.perf_counter()

#%%
sas = saspy.SASsession()

sas.submit("""
%let dsn = census;

libname &dsn. odbc dsn=&dsn. schema=dbo;

proc sql;
    create table acad_calendar as
    select distinct
        *
        ,day(datepart(term_begin_dt)) as begin_day
        ,month(datepart(term_begin_dt)) as begin_month
        ,year(datepart(term_begin_dt)) as begin_year
        ,day(datepart(term_census_dt)) as census_day
        ,month(datepart(term_census_dt)) as census_month
        ,year(datepart(term_census_dt)) as census_year
        ,day(datepart(term_midterm_dt)) as midterm_day
        ,month(datepart(term_midterm_dt)) as midterm_month
        ,year(datepart(term_midterm_dt)) as midterm_year
        ,day(datepart(term_end_dt)) as end_day
        ,month(datepart(term_end_dt)) as end_month
        ,year(datepart(term_end_dt)) as end_year
    from &dsn..xw_term
    where acad_career = 'UGRD'
    order by term_code
;quit;

filename calendar \"Z:\\Nathan\\Models\\student_risk\\supplemental_files\\acad_calendar.csv\" encoding=\"utf-8\";

proc export data=acad_calendar outfile=calendar dbms=csv replace;

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

    if term_type == 'SUM':
        
        try:
            exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\sum\\frsh\\sr_prod_sum_frsh_eot.py').read())
            exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\sum\\tran\\sr_prod_sum_tran_eot.py').read())
        except config.DateError as eot_error:
            print(eot_error)
            config.eot_flag = True
        
        except KeyError as key_error:
            print(key_error)
        except:
            traceback.print_exc(file=sys.stdout)
        else:
            stop = time.perf_counter()
            print(f'Completed in {(stop - start)/60:.1f} minutes\n')

    if term_type == 'SPR':

        try:
            exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\spr\\frsh\\sr_prod_spr_frsh_mid.py').read())
            exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\spr\\tran\\sr_prod_spr_tran_mid.py').read())
        except config.DateError as mid_error:
            print(mid_error)
            config.mid_flag = True
            
            try: 
                exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\spr\\frsh\\sr_prod_spr_frsh_mid.py').read())
                exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\spr\\tran\\sr_prod_spr_tran_mid.py').read())
            except config.DataError as mid_snap_error:
                print(mid_snap_error)

                try:
                    exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\spr\\frsh\\sr_prod_spr_frsh_cen.py').read())
                    exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\spr\\tran\\sr_prod_spr_tran_cen.py').read())
                except config.DateError as cen_error:
                    print(cen_error)
                    config.cen_flag = True
                    
                    try: 
                        exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\spr\\frsh\\sr_prod_spr_frsh_cen.py').read())
                        exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\spr\\tran\\sr_prod_spr_tran_cen.py').read())
                    except config.DataError as cen_snap_error:
                        print(cen_snap_error)
            
                        try:
                            exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\spr\\frsh\\sr_prod_spr_frsh_eot.py').read())
                            exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\spr\\tran\\sr_prod_spr_tran_eot.py').read())
                        except config.DateError as eot_error:
                            print(eot_error)
                            config.eot_flag = True

                            try: 
                                exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\spr\\frsh\\sr_prod_spr_frsh_eot.py').read())
                                exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\spr\\tran\\sr_prod_spr_tran_eot.py').read())
                            except config.DataError as eot_snap_error:
                                print(eot_snap_error)
        
        except KeyError as key_error:
            print(key_error)
        except:
            traceback.print_exc(file=sys.stdout)
        else:
            stop = time.perf_counter()
            print(f'Completed in {(stop - start)/60:.1f} minutes\n')

    if term_type == 'FAL':

        try:
            exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\fal\\frsh\\sr_prod_fal_frsh_mid.py').read())
            exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\fal\\tran\\sr_prod_fal_tran_mid.py').read())
        except config.DateError as mid_error:
            print(mid_error)
            config.mid_flag = True

            try: 
                exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\fal\\frsh\\sr_prod_fal_frsh_mid.py').read())
                exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\fal\\tran\\sr_prod_fal_tran_mid.py').read())
            except config.DataError as mid_snap_error:
                print(mid_snap_error)

                try:
                    exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\fal\\frsh\\sr_prod_fal_frsh_cen.py').read())
                    exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\fal\\tran\\sr_prod_fal_tran_cen.py').read())
                except config.DateError as cen_error:
                    print(cen_error)
                    config.cen_flag = True

                    try: 
                        exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\fal\\frsh\\sr_prod_fal_frsh_cen.py').read())
                        exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\fal\\tran\\sr_prod_fal_tran_cen.py').read())
                    except config.DataError as cen_snap_error:
                        print(cen_snap_error)

                        try:
                            exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\fal\\frsh\\sr_prod_fal_frsh_adm.py').read())
                            exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\fal\\tran\\sr_prod_fal_tran_adm.py').read())
                        except config.DateError as adm_error:
                            print(adm_error)
        
        except KeyError as key_error:
            print(key_error)
        except:
            traceback.print_exc(file=sys.stdout)
        else:
            stop = time.perf_counter()
            print(f'Completed in {(stop - start)/60:.1f} minutes\n')