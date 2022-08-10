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
libname acs \"Z:\\Nathan\\Models\\student_risk\\supplemental_files\\\";

proc sort data=adm.xw_term out=work.xw_term;
	by acad_career strm;
run;

data work.xw_term;
	set work.xw_term;
	by acad_career;
	if first.acad_career then idx = 1;
	else idx + 1;
	where acad_career = 'UGRD';
run;

proc sql;
	create table acs.adj_term as
	select
		base.acad_career,
		base.term_year,
        base.term_type,
        base.strm,
		base.full_acad_year,
		datepart(base.term_begin_dt) as term_begin_dt format=mmddyyd10.,
		datepart(intnx('dtday', next.term_begin_dt, -1)) as term_switch_dt format=mmddyyd10.,
		day(datepart(base.term_begin_dt)) as begin_day,
		week(datepart(base.term_begin_dt)) as begin_week,
		month(datepart(base.term_begin_dt)) as begin_month,
		year(datepart(base.term_begin_dt)) as begin_year,
        day(datepart(base.term_midterm_dt)) as midterm_day,
        week(datepart(base.term_midterm_dt)) as midterm_week,
        month(datepart(base.term_midterm_dt)) as midterm_month,
        year(datepart(base.term_midterm_dt)) as midterm_year,
		day(datepart(intnx('dtday', next.term_begin_dt, -1))) as end_day,
		week(datepart(intnx('dtday', next.term_begin_dt, -1))) as end_week,
		month(datepart(intnx('dtday', next.term_begin_dt, -1))) as end_month,
		year(datepart(intnx('dtday', next.term_begin_dt, -1))) as end_year
	from work.xw_term as base
	left join work.xw_term as next
		on base.acad_career = next.acad_career
		and base.idx = next.idx - 1
;quit;

filename adj_term \"Z:\\Nathan\\Models\\student_risk\\supplemental_files\\acad_calendar.csv\" encoding=\"utf-8\";

proc export data=acs.adj_term outfile=adj_term dbms=csv replace;

proc sql;
	select term_type into: term_type 
	from acs.adj_term 
	where term_year = year(today())
		and begin_month <= month(today()) 
		and end_month >= month(today()) 
		and begin_week <= week(today())
		and end_week >= week(today())
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
