#%%
import sys
import time
import traceback
from datetime import date

import saspy

from student_risk import config

#%%
start = time.perf_counter()

#%%
sas = saspy.SASsession()

sas.submit("""
%let adm = adm;

libname &adm. odbc dsn=&adm. schema=dbo;

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
    from &adm..xw_term
    where acad_career = 'UGRD'
    order by term_code
;quit;

filename calendar \"Z:\\Nathan\\Models\\student_risk\\supplemental_files\\acad_calendar.csv\" encoding=\"utf-8\";

proc export data=acad_calendar outfile=calendar dbms=csv replace;

proc sql;
    select max(term_type) into: term_type 
    from &adm..xw_term 
    where term_year = year(today())
        and month(datepart(term_begin_dt)) <= month(today()) 
        and month(datepart(term_end_dt)) >= month(today()) 
        and week(datepart(term_begin_dt)) <= week(today())
        and acad_career = 'UGRD'
;quit;
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


#%%
if __name__ == '__main__':

    if term_type == 'SUM':
        
        sys.stdout = Logger()

        try:
            exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\sum\\frst\\sr_prod_sum_frst_eot.py').read())
            exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\sum\\tran\\sr_prod_sum_tran_eot.py').read())
        except config.EOTError as eot_error:
            print(eot_error)

        except KeyError as key_error:
            print(key_error)
        except:
            traceback.print_exc(file=sys.stdout)
        else:
            stop = time.perf_counter()
            print(f'Completed in {(stop - start)/60:.1f} minutes\n')

    if term_type == 'SPR':

        sys.stdout = Logger()

        try:
            exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\spr\\frst\\sr_prod_spr_frst_mid.py').read())
            exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\spr\\tran\\sr_prod_spr_tran_mid.py').read())
        except config.MidError as mid_error:
            print(mid_error)

            try:
                exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\spr\\frst\\sr_prod_spr_frst_cen.py').read())
                exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\spr\\tran\\sr_prod_spr_tran_cen.py').read())
            except config.CenError as cen_error:
                print(cen_error)
            
                try:
                    exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\spr\\frst\\sr_prod_spr_frst_eot.py').read())
                    exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\spr\\tran\\sr_prod_spr_tran_eot.py').read())
                except config.EOTError as eot_error:
                    print(eot_error)

                except KeyError as key_error:
                    print(key_error)
                except:
                    traceback.print_exc(file=sys.stdout)
                else:
                    stop = time.perf_counter()
                    print(f'Completed in {(stop - start)/60:.1f} minutes\n')

            except KeyError as key_error:
                print(key_error)
            except:
                traceback.print_exc(file=sys.stdout)
            else:
                stop = time.perf_counter()
                print(f'Completed in {(stop - start)/60:.1f} minutes\n')

        except KeyError as key_error:
            print(key_error)
        except:
            traceback.print_exc(file=sys.stdout)
        else:
            stop = time.perf_counter()
            print(f'Completed in {(stop - start)/60:.1f} minutes\n')

    if term_type == 'FAL':
        
        sys.stdout = Logger()

        try:
            exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\fal\\frst\\sr_prod_fal_frst_mid.py').read())
            exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\fal\\tran\\sr_prod_fal_tran_mid.py').read())
        except config.MidError as mid_error:
            print(mid_error)

            try:
                exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\fal\\frst\\sr_prod_fal_frst_cen.py').read())
                exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\fal\\tran\\sr_prod_fal_tran_cen.py').read())
                exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\fal\\soph\\sr_prod_fal_soph_cen.py').read())
            except config.CenError as cen_error:
                print(cen_error)

                try:
                    exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\fal\\frst\\sr_prod_fal_frst_adm.py').read())
                    exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\fal\\tran\\sr_prod_fal_tran_adm.py').read())
                    exec(open('Z:\\Nathan\\Models\\student_risk\\student_risk\\prod\\fal\\soph\\sr_prod_fal_soph_adm.py').read())
                except config.AdmError as adm_error:
                    print(adm_error)

                except KeyError as key_error:
                    print(key_error)
                except:
                    traceback.print_exc(file=sys.stdout)
                else:
                    stop = time.perf_counter()
                    print(f'Completed in {(stop - start)/60:.1f} minutes\n')

            except KeyError as key_error:
                print(key_error)
            except:
                traceback.print_exc(file=sys.stdout)
            else:
                stop = time.perf_counter()
                print(f'Completed in {(stop - start)/60:.1f} minutes\n')

        except KeyError as key_error:
            print(key_error)
        except:
            traceback.print_exc(file=sys.stdout)
        else:
            stop = time.perf_counter()
            print(f'Completed in {(stop - start)/60:.1f} minutes\n')
