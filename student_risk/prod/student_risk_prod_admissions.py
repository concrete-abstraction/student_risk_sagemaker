#%%
import config
import datetime
import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pathlib
import pyodbc
import os
import saspy
import sklearn
import sqlalchemy
import sys
import time
import urllib
from datetime import date
from patsy import dmatrices
from IPython.display import HTML
from imblearn.over_sampling import SMOTENC
from imblearn.under_sampling import RandomUnderSampler, TomekLinks
from matplotlib.legend_handler import HandlerLine2D
from sklearn.compose import make_column_transformer
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import MinMaxScaler, StandardScaler, OneHotEncoder
from sklearn.linear_model import LinearRegression, LogisticRegression, SGDClassifier
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.ensemble import VotingClassifier
from sklearn.metrics import confusion_matrix, roc_curve, roc_auc_score
from sklearn.model_selection import cross_val_score
from sklearn.model_selection import GridSearchCV
from statsmodels.discrete.discrete_model import Logit
from statsmodels.stats.outliers_influence import variance_inflation_factor

#%%
# Database connection
cred = pathlib.Path('login.bin').read_text().split('|')
params = urllib.parse.quote_plus(f'TRUSTED_CONNECTION=YES; DRIVER={{SQL Server Native Client 11.0}}; SERVER={cred[0]}; DATABASE={cred[1]}')
engine = sqlalchemy.create_engine(f'mssql+pyodbc:///?odbc_connect={params}')
auto_engine = engine.execution_options(autocommit=True, isolation_level='AUTOCOMMIT')

#%%
# Admissions date check
calendar = pd.read_csv('Z:\\Nathan\\Models\\student_risk\\supplemental_files\\acad_calendar.csv', encoding='utf-8', parse_dates=True)
now = datetime.datetime.now()

now_day = now.day
now_month = now.month
now_year = now.year

admissions_day = calendar[(calendar['term_year'] == now_year) & (calendar['begin_month'] <= now_month) & (calendar['end_month'] > now_month)]['begin_day'].values[0]
admissions_month = calendar[(calendar['term_year'] == now_year) & (calendar['begin_month'] <= now_month) & (calendar['end_month'] > now_month)]['begin_month'].values[0]
admissions_year = calendar[(calendar['term_year'] == now_year) & (calendar['begin_month'] <= now_month) & (calendar['end_month'] > now_month)]['begin_year'].values[0]

census_day = calendar[(calendar['term_year'] == now_year) & (calendar['begin_month'] <= now_month) & (calendar['end_month'] > now_month)]['census_day'].values[0]
census_month = calendar[(calendar['term_year'] == now_year) & (calendar['begin_month'] <= now_month) & (calendar['end_month'] > now_month)]['census_month'].values[0]
census_year = calendar[(calendar['term_year'] == now_year) & (calendar['begin_month'] <= now_month) & (calendar['end_month'] > now_month)]['census_year'].values[0]

if now_year < admissions_year or now_year > census_year:
	raise config.DateError(f'{date.today()}: Admissions year exception, outside of date range.')

elif (now_year == admissions_year and now_month < admissions_month) or (now_year == census_year and now_month > census_month):
	raise config.DateError(f'{date.today()}: Admissions month exception, outside of date range.')

elif (now_year == admissions_year and now_month == admissions_month and now_day < admissions_day) or (now_year == census_year and now_month == census_month and now_day >= census_day):
	raise config.DateError(f'{date.today()}: Admissions day exception, outside of date range.')

else:
	print(f'{date.today()}: No admissions date exceptions, running from admissions.')

#%%
# Start SAS session
print('\nStart SAS session...')

sas = saspy.SASsession()

#%%
# Set macro variables
print('Set macro variables...')

sas.submit("""
%let dsn = census;
%let dev = cendev;
%let adm = adm;
%let acs_lag = 2;
%let lag_year = 1;
%let start_cohort = 2015;
%let end_cohort = 2020;
""")

print('Done\n')

#%%
# Set libname statements
print('Set libname statements...')

sas.submit("""
libname &dsn. odbc dsn=&dsn. schema=dbo;
libname &dev. odbc dsn=&dev. schema=dbo;
libname &adm. odbc dsn=&adm. schema=dbo;
libname acs \"Z:\\Nathan\\Models\\student_risk\\supplemental_files\\\";
""")

print('Done\n')

#%%
# Import supplemental files
print('Import supplemental files...')
start = time.perf_counter()

sas.submit("""
proc import out=act_to_sat_engl_read
    datafile=\"Z:\\Nathan\\Models\\student_risk\\supplemental_files\\act_to_sat_engl_read.xlsx\"
    dbms=XLSX REPLACE;
    getnames=YES;
    run;
""")

sas.submit("""
proc import out=act_to_sat_math
    datafile=\"Z:\\Nathan\\Models\\student_risk\\supplemental_files\\act_to_sat_math.xlsx\"
    dbms=XLSX REPLACE;
    getnames=YES;
    run;
""")

sas.submit("""
proc import out=cpi
	datafile=\"Z:\\Nathan\\Models\\student_risk\\supplemental_files\\cpi.xlsx\"
	dbms=XLSX REPLACE;
	getnames=YES;
run;
""")

stop = time.perf_counter()
print(f'Done in {stop - start:.2f} seconds\n')

#%%
# Create SAS macro
print('Create SAS macro...')

sas.submit("""
%macro loop;
	
	%do cohort_year=&start_cohort. %to &end_cohort.;
	
	proc sql;
		create table cohort_&cohort_year. as
		select distinct a.*,
			substr(a.last_sch_postal,1,5) as targetid,
			case when a.sex = 'M' then 1 
				else 0
			end as male,
			case when a.age < 18.25 then 'Q1'
				when 18.25 <= a.age < 18.5 then 'Q2'
				when 18.5 <= a.age < 18.75 then 'Q3'
				when 18.75 <= a.age then 'Q4'
				else 'missing'
			end as age_group,
			case when a.father_attended_wsu_flag = 'Y' then 1 
				else 0
			end as father_wsu_flag,
			case when a.mother_attended_wsu_flag = 'Y' then 1 
				else 0
			end as mother_wsu_flag,
			case when a.ipeds_ethnic_group in ('2', '3', '5', '7', 'Z') then 1 
				else 0
			end as underrep_minority,
			case when a.WA_residency = 'RES' then 1
				else 0
			end as resident,
			case when a.adm_parent1_highest_educ_lvl in ('B','C','D','E','F') then '< bach'
				when a.adm_parent1_highest_educ_lvl = 'G' then 'bach'
				when a.adm_parent1_highest_educ_lvl in ('H','I','J','K','L') then '> bach'
					else 'missing'
			end as parent1_highest_educ_lvl,
			case when a.adm_parent2_highest_educ_lvl in ('B','C','D','E','F') then '< bach'
				when a.adm_parent2_highest_educ_lvl = 'G' then 'bach'
				when a.adm_parent2_highest_educ_lvl in ('H','I','J','K','L') then '> bach'
					else 'missing'
			end as parent2_highest_educ_lvl,
			b.distance,
			l.cpi_2018_adj,
			c.median_inc as median_inc_wo_cpi,
			c.median_inc*l.cpi_2018_adj as median_inc,
			c.gini_indx,
			d.pvrt_total/d.pvrt_base as pvrt_rate,
			e.educ_total/e.educ_base as educ_rate,
			f.pop/(g.area*3.861E-7) as pop_dens,
			h.median_value as median_value_wo_cpi,
			h.median_value*l.cpi_2018_adj as median_value,
			i.race_blk/i.race_tot as pct_blk,
			i.race_ai/i.race_tot as pct_ai,
			i.race_asn/i.race_tot as pct_asn,
			i.race_hawi/i.race_tot as pct_hawi,
			i.race_oth/i.race_tot as pct_oth,
			i.race_two/i.race_tot as pct_two,
			(i.race_blk + i.race_ai + i.race_asn + i.race_hawi + i.race_oth + i.race_two)/i.race_tot as pct_non,
			j.ethnic_hisp/j.ethnic_tot as pct_hisp,
			case when k.locale = '11' then 1 else 0 end as city_large,
			case when k.locale = '12' then 1 else 0 end as city_mid,
			case when k.locale = '13' then 1 else 0 end as city_small,
			case when k.locale = '21' then 1 else 0 end as suburb_large,
			case when k.locale = '22' then 1 else 0 end as suburb_mid,
			case when k.locale = '23' then 1 else 0 end as suburb_small,
			case when k.locale = '31' then 1 else 0 end as town_fringe,
			case when k.locale = '32' then 1 else 0 end as town_distant,
			case when k.locale = '33' then 1 else 0 end as town_remote,
			case when k.locale = '41' then 1 else 0 end as rural_fringe,
			case when k.locale = '42' then 1 else 0 end as rural_distant,
			case when k.locale = '43' then 1 else 0 end as rural_remote
		from &dsn..new_student_enrolled_vw as a
		left join acs.distance as b
			on substr(a.last_sch_postal,1,5) = b.targetid
		left join acs.acs_income_%eval(&cohort_year. - &acs_lag.) as c
			on substr(a.last_sch_postal,1,5) = c.geoid
		left join acs.acs_poverty_%eval(&cohort_year. - &acs_lag.) as d
			on substr(a.last_sch_postal,1,5) = d.geoid
		left join acs.acs_education_%eval(&cohort_year. - &acs_lag.) as e
			on substr(a.last_sch_postal,1,5) = e.geoid
		left join acs.acs_demo_%eval(&cohort_year. - &acs_lag.) as f
			on substr(a.last_sch_postal,1,5) = f.geoid
		left join acs.acs_area_%eval(&cohort_year. - &acs_lag.) as g
			on substr(a.last_sch_postal,1,5) = g.geoid
		left join acs.acs_housing_%eval(&cohort_year. - &acs_lag.) as h
			on substr(a.last_sch_postal,1,5) = h.geoid
		left join acs.acs_race_%eval(&cohort_year. - &acs_lag.) as i
			on substr(a.last_sch_postal,1,5) = i.geoid
		left join acs.acs_ethnicity_%eval(&cohort_year. - &acs_lag.) as j
			on substr(a.last_sch_postal,1,5) = j.geoid
		left join acs.edge_locale14_zcta_table as k
			on substr(a.last_sch_postal,1,5) = k.zcta5ce10
		left join cpi as l
			on input(a.full_acad_year, 4.) = l.acs_lag
		where a.full_acad_year = "&cohort_year"
			and substr(a.strm, 4 , 1) = '7'
			and a.adj_admit_campus = 'PULLM'
			and a.acad_career = 'UGRD'
			and a.adj_admit_type_cat = 'FRSH'
			and a.ipeds_full_part_time = 'F'
			and a.ipeds_ind = 1
			and a.term_credit_hours > 0
		order by a.emplid
	;quit;
	
	proc sql;
		create table new_student_&cohort_year. as
		select distinct
			emplid,
			pell_recipient_ind,
			eot_term_gpa,
			eot_term_gpa_hours
		from &dev..new_student_profile_ugrd
		where substr(strm, 4 , 1) = '7'
			and adj_admit_campus = 'PULLM'
			and adj_admit_type = 'FRS'
			and ipeds_full_part_time = 'F'
	;quit;
	
	%if &cohort_year. < &end_cohort. %then %do;
		proc sql;
			create table enrolled_&cohort_year. as
			select distinct 
				emplid, 
				term_code as cont_term,
				enrl_ind
			from &dsn..student_enrolled_vw
			where snapshot = 'census'
				and full_acad_year = put(%eval(&cohort_year. + &lag_year.), 4.)
				and substr(strm, 4, 1) = '7'
				and acad_career = 'UGRD'
				and new_continue_status = 'CTU'
				and term_credit_hours > 0
			order by emplid
		;quit;
	%end;

	%if &cohort_year. = &end_cohort. %then %do;
		proc sql;
			create table enrolled_&cohort_year. as
			select distinct 
				emplid, 
				input(substr(strm, 1, 1) || '0' || substr(strm, 2, 2) || '3', 5.) as cont_term,
				enrl_ind
			from acs.enrl_data
			where substr(strm, 4, 1) = '7'
				and acad_career = 'UGRD'
			order by emplid
		;quit;
	%end;

	proc sql;
		create table race_detail_&cohort_year. as
		select 
			a.emplid,
			case when hispc.emplid is not null 	then 'Y'
												else 'N'
												end as race_hispanic,
			case when amind.emplid is not null then 'Y'
											   else 'N'
											   end as race_american_indian,
			case when alask.emplid is not null then 'Y'
											   else 'N'
											   end as race_alaska,
			case when asian.emplid is not null then 'Y'
											   else 'N'
											   end as race_asian,
			case when black.emplid is not null then 'Y'
											   else 'N'
											   end as race_black,
			case when hawai.emplid is not null then 'Y'
											   else 'N'
											   end as race_native_hawaiian,
			case when white.emplid is not null then 'Y'
											   else 'N'
											   end as race_white
		from cohort_&cohort_year. as a
		left join (select distinct e4.emplid from &dsn..student_ethnic_detail as e4
					left join &dsn..xw_ethnic_detail_to_group_vw as xe4
						on e4.ethnic_cd = xe4.ethnic_cd
					where e4.snapshot = 'census'
						and e4.strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
						and xe4.ethnic_group = '4') as asian
			on a.emplid = asian.emplid
		left join (select distinct e2.emplid from &dsn..student_ethnic_detail as e2
					left join &dsn..xw_ethnic_detail_to_group_vw as xe2
						on e2.ethnic_cd = xe2.ethnic_cd
					where e2.snapshot = 'census'
						and e2.strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
						and xe2.ethnic_group = '2') as black
			on a.emplid = black.emplid
		left join (select distinct e7.emplid from &dsn..student_ethnic_detail as e7
					left join &dsn..xw_ethnic_detail_to_group_vw as xe7
						on e7.ethnic_cd = xe7.ethnic_cd
					where e7.snapshot = 'census'
						and e7.strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
						and xe7.ethnic_group = '7') as hawai
			on a.emplid = hawai.emplid
		left join (select distinct e1.emplid from &dsn..student_ethnic_detail as e1
					left join &dsn..xw_ethnic_detail_to_group_vw as xe1
						on e1.ethnic_cd = xe1.ethnic_cd
					where e1.snapshot = 'census'
						and e1.strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
						and xe1.ethnic_group = '1') as white
			on a.emplid = white.emplid
		left join (select distinct e5a.emplid from &dsn..student_ethnic_detail as e5a
					left join &dsn..xw_ethnic_detail_to_group_vw as xe5a
						on e5a.ethnic_cd = xe5a.ethnic_cd
					where e5a.snapshot = 'census' 
						and e5a.strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
						and xe5a.ethnic_group = '5'
						and e5a.ethnic_cd in ('014','016','017','018',
												'935','941','942','943',
												'950','R10','R14')) as alask
			on a.emplid = alask.emplid
		left join (select distinct e5b.emplid from &dsn..student_ethnic_detail as e5b
					left join &dsn..xw_ethnic_detail_to_group_vw as xe5b
						on e5b.ethnic_cd = xe5b.ethnic_cd
					where e5b.snapshot = 'census'
						and e5b.strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
						and xe5b.ethnic_group = '5'
						and e5b.ethnic_cd not in ('014','016','017','018',
													'935','941','942','943',
													'950','R14')) as amind
			on a.emplid = amind.emplid
		left join (select distinct e6.emplid from &dsn..student_ethnic_detail as e6
					left join &dsn..xw_ethnic_detail_to_group_vw as xe6
						on e6.ethnic_cd = xe6.ethnic_cd
					where e6.snapshot = 'census'
						and e6.strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
						and xe6.ethnic_group = '3') as hispc
			on a.emplid = hispc.emplid
	;quit;
	
	proc sql;
		create table plan_&cohort_year. as 
		select distinct 
			emplid,
			acad_plan,
			acad_plan_descr,
			plan_owner_org,
			plan_owner_org_descr,
			plan_owner_group_descrshort,
			case when plan_owner_group_descrshort = 'Business' then 1 else 0 end as business,
			case when plan_owner_group_descrshort = 'CAHNREXT' 
				and plan_owner_org = '03_1240' then 1 else 0 end as cahnrs_anml,
			case when plan_owner_group_descrshort = 'CAHNREXT' 
				and plan_owner_org = '03_1990' then 1 else 0 end as cahnrs_envr,
			case when plan_owner_group_descrshort = 'CAHNREXT' 
				and plan_owner_org = '03_1150' then 1 else 0 end as cahnrs_econ,	
			case when plan_owner_group_descrshort = 'CAHNREXT'
				and plan_owner_org not in ('03_1240','03_1990','03_1150') then 1 else 0 end as cahnrext,
			case when plan_owner_group_descrshort = 'CAS'
				and plan_owner_org = '31_1540' then 1 else 0 end as cas_chem,
			case when plan_owner_group_descrshort = 'CAS'
				and plan_owner_org = '31_1710' then 1 else 0 end as cas_crim,
			case when plan_owner_group_descrshort = 'CAS'
				and plan_owner_org = '31_2530' then 1 else 0 end as cas_math,
			case when plan_owner_group_descrshort = 'CAS'
				and plan_owner_org = '31_2900' then 1 else 0 end as cas_psyc,
			case when plan_owner_group_descrshort = 'CAS'
				and plan_owner_org = '31_8434' then 1 else 0 end as cas_biol,
			case when plan_owner_group_descrshort = 'CAS'
				and plan_owner_org = '31_1830' then 1 else 0 end as cas_engl,
			case when plan_owner_group_descrshort = 'CAS'
				and plan_owner_org = '31_2790' then 1 else 0 end as cas_phys,	
			case when plan_owner_group_descrshort = 'CAS'
				and plan_owner_org not in ('31_1540','31_1710','31_2530','31_2900','31_8434','31_1830','31_2790') then 1 else 0 end as cas,
			case when plan_owner_group_descrshort = 'Comm' then 1 else 0 end as comm,
			case when plan_owner_group_descrshort = 'Education' then 1 else 0 end as education,
			case when plan_owner_group_descrshort in ('Med Sci','Medicine') then 1 else 0 end as medicine,
			case when plan_owner_group_descrshort = 'Nursing' then 1 else 0 end as nursing,
			case when plan_owner_group_descrshort = 'Pharmacy' then 1 else 0 end as pharmacy,
			case when plan_owner_group_descrshort = 'Provost' then 1 else 0 end as provost,
			case when plan_owner_group_descrshort = 'VCEA' 
				and plan_owner_org = '05_1520' then 1 else 0 end as vcea_bioe,
			case when plan_owner_group_descrshort = 'VCEA' 
				and plan_owner_org = '05_1590' then 1 else 0 end as vcea_cive,
			case when plan_owner_group_descrshort = 'VCEA' 
				and plan_owner_org = '05_1260' then 1 else 0 end as vcea_desn,
			case when plan_owner_group_descrshort = 'VCEA' 
				and plan_owner_org = '05_1770' then 1 else 0 end as vcea_eecs,
			case when plan_owner_group_descrshort = 'VCEA' 
				and plan_owner_org = '05_2540' then 1 else 0 end as vcea_mech,
			case when plan_owner_group_descrshort = 'VCEA' 
				and plan_owner_org not in ('05_1520','05_1590','05_1260','05_1770','05_2540') then 1 else 0 end as vcea,				
			case when plan_owner_group_descrshort = 'Vet Med' then 1 else 0 end as vet_med,
			case when plan_owner_group_descrshort not in ('Business','CAHNREXT','CAS','Comm',
														'Education','Med Sci','Medicine','Nursing',
														'Pharmacy','Provost','VCEA','Vet Med') then 1 else 0
			end as groupless,
			case when plan_owner_percent_owned = 50 and plan_owner_org in ('05_1770','03_1990','12_8595') then 1 else 0
			end as split_plan,
			lsamp_stem_flag,
			anywhere_stem_flag
		from &dsn..student_acad_prog_plan_vw
		where snapshot = 'census'
			and full_acad_year = "&cohort_year." /* Note: Was aid_year previously? Why? Check! */
			and substr(strm, 4, 1) = '7'
			and adj_admit_campus = 'PULLM'
			and acad_career = 'UGRD'
			and adj_admit_type_cat = 'FRSH'
			and primary_plan_flag = 'Y'
			and calculated split_plan = 0
	;quit;
	
	proc sql;
		create table need_&cohort_year. as
		select distinct
			a.emplid,
			b.snapshot as need_snap,
			a.aid_year,
			a.fed_efc,
			a.fed_need
		from &dsn..fa_award_period as a
		inner join (select distinct emplid, aid_year, min(snapshot) as snapshot from &dsn..fa_award_period where aid_year = "&cohort_year.") as b
			on a.emplid = b.emplid
				and a.aid_year = b.aid_year
				and a.snapshot = b.snapshot
		where a.aid_year = "&cohort_year."	
			and a.award_period in ('A','B')
			and a.efc_status = 'O'
	;quit;
	
	proc sql;
		create table aid_&cohort_year. as
		select distinct
			a.emplid,
			b.snapshot as aid_snap,
			a.aid_year,
			sum(a.disbursed_amt) as total_disb,
			sum(a.offer_amt) as total_offer,
			sum(a.accept_amt) as total_accept
		from &dsn..fa_award_aid_year_vw as a
		inner join (select distinct emplid, aid_year, min(snapshot) as snapshot from &dsn..fa_award_aid_year_vw where aid_year = "&cohort_year.") as b
			on a.emplid = b.emplid
				and a.aid_year = b.aid_year
				and a.snapshot = b.snapshot
		where a.aid_year = "&cohort_year."
			and a.award_period in ('A','B')
			and a.award_status = 'A'
		group by a.emplid;
	;quit;
	
	proc sql;
		create table exams_&cohort_year. as 
		select distinct
			a.emplid,
			a.best,
			a.bestr,
			a.qvalue,
			a.act_engl,
			a.act_read,
			a.act_math,
			largest(1, a.sat_erws, xw_one.sat_erws, xw_three.sat_erws) as sat_erws,
			largest(1, a.sat_mss, xw_two.sat_mss, xw_four.sat_mss) as sat_mss,
			largest(1, (a.sat_erws + a.sat_mss), (xw_one.sat_erws + xw_two.sat_mss), (xw_three.sat_erws + xw_four.sat_mss)) as sat_comp
		from &dsn..new_freshmen_test_score_vw as a
		left join &dsn..xw_sat_i_to_sat_erws as xw_one
			on (a.sat_i_verb + a.sat_i_wr) = xw_one.sat_i_verb_plus_wr
		left join &dsn..xw_sat_i_to_sat_mss as xw_two
 			on a.sat_i_math = xw_two.sat_i_math
 		left join act_to_sat_engl_read as xw_three
 			on (a.act_engl + a.act_read) = xw_three.act_engl_read
		left join act_to_sat_math as xw_four
 			on a.act_math = xw_four.act_math
		where snapshot = 'census'
	;quit;

	proc sql;
		create table degrees_&cohort_year. as
		select distinct
			emplid,
			case when degree = 'AD_AS-T' then 'AD_AST' else degree end as degree,
			1 as ind
		from &dsn..student_ext_degree
		where floor(degree_term_code / 10) <= &cohort_year.
			and degree in ('AD_AS-T','AD_DTA')
		order by emplid
	;quit;
	
	proc transpose data=degrees_&cohort_year. let out=degrees_&cohort_year. (drop=_name_);
		by emplid;
		id degree;
	run;
	
	proc sql;
		create table preparatory_&cohort_year. as
		select distinct
			emplid,
			ext_subject_area,
			1 as ind
		from &dsn..student_ext_acad_subj
		where snapshot = 'census'
			and ext_subject_area in ('CHS','RS', 'AP','IB','AICE')
		order by emplid
	;quit;
	
	proc transpose data=preparatory_&cohort_year. let out=preparatory_&cohort_year. (drop=_name_);
		by emplid;
		id ext_subject_area;
	run;
	
	proc sql;
		create table visitation_&cohort_year. as
		select distinct a.emplid,
			b.snap_date,
			a.attendee_afr_am_scholars_visit,
			a.attendee_alive,
			a.attendee_campus_visit,
			a.attendee_cashe,
			a.attendee_destination,
			a.attendee_experience,
			a.attendee_fcd_pullman,
			a.attendee_fced,
			a.attendee_fcoc,
			a.attendee_fcod,
			a.attendee_group_visit,
			a.attendee_honors_visit,
			a.attendee_imagine_tomorrow,
			a.attendee_imagine_u,
			a.attendee_la_bienvenida,
			a.attendee_lvp_camp,
			a.attendee_oos_destination,
			a.attendee_oos_experience,
			a.attendee_preview,
			a.attendee_preview_jrs,
			a.attendee_shaping,
			a.attendee_top_scholars,
			a.attendee_transfer_day,
			a.attendee_vibes,
			a.attendee_welcome_center,
			a.attendee_any_visitation_ind,
			a.attendee_total_visits
		from &adm..UGRD_visitation_attendee as a
		inner join (select distinct emplid, max(snap_date) as snap_date 
					from &adm..UGRD_visitation_attendee 
					where strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
					group by emplid) as b
			on a.emplid = b.emplid
				and a.snap_date = b.snap_date
		where strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
	;quit;
	
	proc sql;
		create table visitation_detail_&cohort_year. as
		select distinct a.emplid,
			a.snap_date,
			a.go2,
			a.ocv_dt,
			a.ocv_fcd,
			a.ocv_fprv,
			a.ocv_gdt,
			a.ocv_jprv,
			a.ri_col,
			a.ri_fair,
			a.ri_hsv,
			a.ri_nac,
			a.ri_wac,
			a.ri_other,
			a.tap,
			a.tst,
			a.vi_chegg,
			a.vi_crn,
			a.vi_cxc,
			a.vi_mco,
			a.np_group,
			a.out_group,
			a.ref_group,
			a.ocv_da,
			a.ocv_ea,
			a.ocv_fced,
			a.ocv_fcoc,
			a.ocv_fcod,
			a.ocv_oosd,
			a.ocv_oose,
			a.ocv_ve
		from &adm..UGRD_visitation as a
		inner join (select distinct emplid, max(snap_date) as snap_date 
					from &adm..UGRD_visitation 
					where strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
					group by emplid) as b
			on a.emplid = b.emplid
				and a.snap_date = b.snap_date
		where strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
	;quit;
			
	proc sql;
		create table athlete_&cohort_year. as
		select distinct 
			emplid,
			case when (mbaseball = 'Y' 
				or mbasketball = 'Y'
				or mfootball = 'Y'
				or mgolf = 'Y'
				or mitrack = 'Y'
				or motrack = 'Y'
				or mxcountry = 'Y'
				or wbasketball = 'Y'
				or wgolf = 'Y'
				or witrack = 'Y'
				or wotrack = 'Y'
				or wsoccer = 'Y'
				or wswimming = 'Y'
				or wtennis = 'Y'
				or wvolleyball = 'Y'
				or wvrowing = 'Y'
				or wxcountry = 'Y') then 1 else 0
			end as athlete
		from &dsn..student_athlete_vw
		where snapshot = 'census'
			and strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
			and ugrd_adj_admit_type = 'FRS'
	;quit;
	
	proc sql;
		create table remedial_&cohort_year. as
		select distinct
			emplid,
			case when grading_basis_enrl in ('REM','RMS','RMP') 	then 1
																	else 0
																	end as remedial
		from &dsn..class_registration_vw
		where snapshot = 'census'
			and aid_year = "&cohort_year."
			and grading_basis_enrl in ('REM','RMS','RMP')
		order by emplid
	;quit;
	
	proc sql;
		create table date_&cohort_year. as
		select distinct
			min(emplid) as emplid,
			min(week_from_term_begin_dt) as min_week_from_term_begin_dt,
			max(week_from_term_begin_dt) as max_week_from_term_begin_dt,
			count(week_from_term_begin_dt) as count_week_from_term_begin_dt
		from &adm..UGRD_shortened_vw
		where strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
			and ugrd_applicant_counting_ind = 1
		group by emplid
		order by emplid;
	;quit;

	proc sql;
		create table class_registration_&cohort_year. as
		select distinct
			strm,
			emplid,
			class_nbr,
			crse_id,
			subject_catalog_nbr,
			ssr_component
		from &dsn..class_registration_vw
		where snapshot = 'eot'
			and full_acad_year = "&cohort_year."
			and enrl_ind = 1
	;quit;
	
	proc sql;
		create table class_difficulty_&cohort_year. as
		select distinct
			a.subject_catalog_nbr,
			a.ssr_component,
			coalesce(b.total_grade_A, 0) + coalesce(c.total_grade_A, 0) as total_grade_A,
			(calculated total_grade_A * 4.0) as total_grade_A_GPA,
			coalesce(b.total_grade_A_minus, 0) + coalesce(c.total_grade_A_minus, 0) as total_grade_A_minus,
			(calculated total_grade_A_minus * 3.7) as total_grade_A_minus_GPA,
			coalesce(b.total_grade_B_plus, 0) + coalesce(c.total_grade_B_plus, 0) as total_grade_B_plus,
			(calculated total_grade_B_plus * 3.3) as total_grade_B_plus_GPA,
			coalesce(b.total_grade_B, 0) + coalesce(c.total_grade_B, 0) as total_grade_B,
			(calculated total_grade_B * 3.0) as total_grade_B_GPA,
			coalesce(b.total_grade_B_minus, 0) + coalesce(c.total_grade_B_minus, 0) as total_grade_B_minus,
			(calculated total_grade_B_minus * 2.7) as total_grade_B_minus_GPA,
			coalesce(b.total_grade_C_plus, 0) + coalesce(c.total_grade_C_plus, 0) as total_grade_C_plus,
			(calculated total_grade_C_plus * 2.3) as total_grade_C_plus_GPA,
			coalesce(b.total_grade_C, 0) + coalesce(c.total_grade_C, 0) as total_grade_C,
			(calculated total_grade_C * 2.0) as total_grade_C_GPA,
			coalesce(b.total_grade_C_minus, 0) + coalesce(c.total_grade_C_minus, 0) as total_grade_C_minus,
			(calculated total_grade_C_minus * 1.7) as total_grade_C_minus_GPA,
			coalesce(b.total_grade_D_plus, 0) + coalesce(c.total_grade_D_plus, 0) as total_grade_D_plus,
			(calculated total_grade_D_plus * 1.3) as total_grade_D_plus_GPA,
			coalesce(b.total_grade_D, 0) + coalesce(c.total_grade_D, 0) as total_grade_D,
			(calculated total_grade_D * 1.0) as total_grade_D_GPA,
			coalesce(b.total_grade_F, 0) + coalesce(c.total_grade_F, 0) as total_grade_F,
			coalesce(b.total_withdrawn, 0) + coalesce(c.total_withdrawn, 0) as total_withdrawn,
			(calculated total_grade_A + calculated total_grade_A_minus 
				+ calculated total_grade_B_plus + calculated total_grade_B + calculated total_grade_B_minus
				+ calculated total_grade_C_plus + calculated total_grade_C + calculated total_grade_C_minus
				+ calculated total_grade_D_plus + calculated total_grade_D + calculated total_grade_F) as total_grades,
			(calculated total_grade_A + calculated total_grade_A_minus 
				+ calculated total_grade_B_plus + calculated total_grade_B + calculated total_grade_B_minus
				+ calculated total_grade_C_plus + calculated total_grade_C + calculated total_grade_C_minus
				+ calculated total_grade_D_plus + calculated total_grade_D + calculated total_grade_F + calculated total_withdrawn) as total_students,
			(calculated total_grade_A_GPA + calculated total_grade_A_minus_GPA 
				+ calculated total_grade_B_plus_GPA + calculated total_grade_B_GPA + calculated total_grade_B_minus_GPA
				+ calculated total_grade_C_plus_GPA + calculated total_grade_C_GPA + calculated total_grade_C_minus_GPA
				+ calculated total_grade_D_plus_GPA + calculated total_grade_D_GPA) as total_grades_GPA,
			(calculated total_grades_GPA / calculated total_grades) as class_average,
			(calculated total_withdrawn / calculated total_students) as pct_withdrawn,
			(calculated total_grade_C_minus + calculated total_grade_D_plus + calculated total_grade_D 
				+ calculated total_grade_F + calculated total_withdrawn) as CDFW,
			(calculated CDFW / calculated total_students) as pct_CDFW,
			(calculated total_grade_C_minus + calculated total_grade_D_plus + calculated total_grade_D 
				+ calculated total_grade_F) as CDF,
			(calculated CDF / calculated total_students) as pct_CDF,
			(calculated total_grade_D_plus + calculated total_grade_D + calculated total_grade_F 
				+ calculated total_withdrawn) as DFW,
			(calculated DFW / calculated total_students) as pct_DFW,
			(calculated total_grade_D_plus + calculated total_grade_D + calculated total_grade_F) as DF,
			(calculated DF / calculated total_students) as pct_DF
		from &dsn..class_vw as a
		left join (select distinct 
						subject_catalog_nbr,
						ssr_component,
						sum(total_grade_A) as total_grade_A,
						sum(total_grade_A_minus) as total_grade_A_minus,
						sum(total_grade_B_plus) as total_grade_B_plus,
						sum(total_grade_B) as total_grade_B,
						sum(total_grade_B_minus) as total_grade_B_minus,
						sum(total_grade_C_plus) as total_grade_C_plus,
						sum(total_grade_C) as total_grade_C,
						sum(total_grade_C_minus) as total_grade_C_minus,
						sum(total_grade_D_plus) as total_grade_D_plus,
						sum(total_grade_D) as total_grade_D,
						sum(total_grade_F) as total_grade_F,
						sum(total_withdrawn) as total_withdrawn
					from &dsn..class_vw
					where snapshot = 'eot'
						and full_acad_year = put(%eval(&cohort_year. - &lag_year.), 4.)
						and ssr_component = 'LEC'
					group by subject_catalog_nbr) as b
			on a.subject_catalog_nbr = b.subject_catalog_nbr
				and a.ssr_component = b.ssr_component
		left join (select distinct 
						subject_catalog_nbr,
						ssr_component,
						sum(total_grade_A) as total_grade_A,
						sum(total_grade_A_minus) as total_grade_A_minus,
						sum(total_grade_B_plus) as total_grade_B_plus,
						sum(total_grade_B) as total_grade_B,
						sum(total_grade_B_minus) as total_grade_B_minus,
						sum(total_grade_C_plus) as total_grade_C_plus,
						sum(total_grade_C) as total_grade_C,
						sum(total_grade_C_minus) as total_grade_C_minus,
						sum(total_grade_D_plus) as total_grade_D_plus,
						sum(total_grade_D) as total_grade_D,
						sum(total_grade_F) as total_grade_F,
						sum(total_withdrawn) as total_withdrawn
					from &dsn..class_vw
					where snapshot = 'eot'
						and full_acad_year = put(%eval(&cohort_year. - &lag_year.), 4.)
						and ssr_component = 'LAB'
					group by subject_catalog_nbr) as c
			on a.subject_catalog_nbr = c.subject_catalog_nbr
				and a.ssr_component = c.ssr_component
		where a.snapshot = 'eot'
			and a.full_acad_year = "&cohort_year."
			and a.ssr_component in ('LEC','LAB')
		group by a.subject_catalog_nbr
		order by a.subject_catalog_nbr
	;quit;
	
	proc sql;
		create table class_count_&cohort_year. as
		select distinct
			a.emplid,
			count(b.class_nbr) as fall_lec_count,
			count(c.class_nbr) as fall_lab_count,
			count(d.class_nbr) as spring_lec_count,
			count(e.class_nbr) as spring_lab_count,
			coalesce(calculated fall_lec_count, 0) + coalesce(calculated spring_lec_count, 0) as total_lec_count,
			coalesce(calculated fall_lab_count, 0) + coalesce(calculated spring_lab_count, 0) as total_lab_count
		from &dsn..class_registration_vw as a
		left join (select distinct emplid, 
						class_nbr
					from &dsn..class_registration_vw
					where snapshot = 'eot'
						and full_acad_year = "&cohort_year."
						and enrl_ind = 1
						and substr(strm,4,1) = '7'
						and ssr_component = 'LEC') as b
			on a.emplid = b.emplid
				and a.class_nbr = b.class_nbr
		left join (select distinct emplid, 
						class_nbr
					from &dsn..class_registration_vw
					where snapshot = 'eot'
						and full_acad_year = "&cohort_year."
						and enrl_ind = 1
						and substr(strm,4,1) = '7'
						and ssr_component = 'LAB') as c
			on a.emplid = c.emplid
				and a.class_nbr = c.class_nbr
		left join (select distinct emplid, 
						class_nbr
					from &dsn..class_registration_vw
					where snapshot = 'eot'
						and full_acad_year = "&cohort_year."
						and enrl_ind = 1
						and substr(strm,4,1) = '3'
						and ssr_component = 'LEC') as d
			on a.emplid = d.emplid
				and a.class_nbr = d.class_nbr
		left join (select distinct emplid, 
						class_nbr
					from &dsn..class_registration_vw
					where snapshot = 'census'
						and full_acad_year = "&cohort_year."
						and enrl_ind = 1
						and substr(strm,4,1) = '3'
						and ssr_component = 'LAB') as e
			on a.emplid = e.emplid
				and a.class_nbr = e.class_nbr
		where a.snapshot = 'census'
			and a.full_acad_year = "&cohort_year."
			and a.enrl_ind = 1
		group by a.emplid
	;quit;
	
	proc sql;
		create table coursework_difficulty_&cohort_year. as
		select distinct
			a.emplid,
			avg(b.class_average) as avg_difficulty,
			avg(b.pct_withdrawn) as avg_pct_withdrawn,
			avg(b.pct_CDFW) as avg_pct_CDFW,
			avg(b.pct_CDF) as avg_pct_CDF,
			avg(b.pct_DFW) as avg_pct_DFW,
			avg(b.pct_DF) as avg_pct_DF
		from class_registration_&cohort_year. as a
		left join class_difficulty_&cohort_year. as b
			on a.subject_catalog_nbr = b.subject_catalog_nbr
		group by a.emplid
	;quit;
	
	proc sql;
		create table term_contact_hrs_&cohort_year. as
		select distinct
			a.emplid,
			sum(b.lec_contact_hrs) as fall_lec_contact_hrs,
			sum(c.lab_contact_hrs) as fall_lab_contact_hrs,
			sum(d.lec_contact_hrs) as spring_lec_contact_hrs,
			sum(e.lab_contact_hrs) as spring_lab_contact_hrs,
			coalesce(calculated fall_lec_contact_hrs, 0) + coalesce(calculated fall_lab_contact_hrs, 0) as total_fall_contact_hrs,
			coalesce(calculated spring_lec_contact_hrs, 0) + coalesce(calculated spring_lab_contact_hrs, 0) as total_spring_contact_hrs
		from class_registration_&cohort_year. as a
		left join (select distinct
						subject_catalog_nbr,
						max(term_contact_hrs) as lec_contact_hrs,
						ssr_component
					from &dsn..class_vw
					where snapshot = 'eot'
						and full_acad_year = put(%eval(&cohort_year.), 4.)
						and substr(strm,4,1) = '7' 
						and ssr_component = 'LEC'
					group by subject_catalog_nbr) as b
			on a.subject_catalog_nbr = b.subject_catalog_nbr
				and a.ssr_component = b.ssr_component
				and substr(a.strm,4,1) = '7'
		left join (select distinct
						subject_catalog_nbr,
						max(term_contact_hrs) as lab_contact_hrs,
						ssr_component
					from &dsn..class_vw
					where snapshot = 'eot'
						and full_acad_year = put(%eval(&cohort_year.), 4.)
						and substr(strm,4,1) = '7' 
						and ssr_component = 'LAB'
					group by subject_catalog_nbr) as c
			on a.subject_catalog_nbr = c.subject_catalog_nbr
				and a.ssr_component = c.ssr_component
				and substr(a.strm,4,1) = '7'
		left join (select distinct
						subject_catalog_nbr,
						max(term_contact_hrs) as lec_contact_hrs,
						ssr_component
					from &dsn..class_vw
					where snapshot = 'eot'
						and full_acad_year = put(%eval(&cohort_year.), 4.)
						and substr(strm,4,1) = '3' 
						and ssr_component = 'LEC'
					group by subject_catalog_nbr) as d
			on a.subject_catalog_nbr = d.subject_catalog_nbr
				and a.ssr_component = d.ssr_component
				and substr(a.strm,4,1) = '3'
		left join (select distinct
						subject_catalog_nbr,
						max(term_contact_hrs) as lab_contact_hrs,
						ssr_component
					from &dsn..class_vw
					where snapshot = 'eot'
						and full_acad_year = put(%eval(&cohort_year.), 4.)
						and substr(strm,4,1) = '3' 
						and ssr_component = 'LAB'
					group by subject_catalog_nbr) as e
			on a.subject_catalog_nbr = e.subject_catalog_nbr
				and a.ssr_component = e.ssr_component
				and substr(a.strm,4,1) = '3'
		group by a.emplid
	;quit;
	
	proc sql;
		create table exams_detail_&cohort_year. as
		select distinct
			emplid,
			max(sat_sup_rwc) as sat_sup_rwc,
			max(sat_sup_ce) as sat_sup_ce,
			max(sat_sup_ha) as sat_sup_ha,
			max(sat_sup_psda) as sat_sup_psda,
			max(sat_sup_ei) as sat_sup_ei,
			max(sat_sup_pam) as sat_sup_pam,
			max(sat_sup_sec) as sat_sup_sec
		from &dsn..student_test_comp_sat_w
		where snapshot = 'census'
		group by emplid
	;quit;
	
	proc sql;
		create table housing_&cohort_year. as
		select distinct
			emplid,
			camp_addr_indicator,
			housing_reshall_indicator,
			housing_ssa_indicator,
			housing_family_indicator,
			afl_reshall_indicator,
			afl_ssa_indicator,
			afl_family_indicator,
			afl_greek_indicator,
			afl_greek_life_indicator
		from &dsn..new_student_enrolled_housing_vw
		where snapshot = 'census'
			and strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
			and adj_admit_campus = 'PULLM'
			and acad_career = 'UGRD'
			and adj_admit_type_cat = 'FRSH'
	;quit;
	
	proc sql;
		create table housing_detail_&cohort_year. as
		select distinct
			emplid,
			'#' || put(building_id, z2.) as building_id
		from &dsn..student_housing
		where snapshot = 'census'
			and strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
	;quit;
	
	proc sql;
		create table dataset_&cohort_year. as
		select 
			a.*,
			b.pell_recipient_ind,
			b.eot_term_gpa,
			b.eot_term_gpa_hours,
			c.cont_term,
			c.enrl_ind,
			d.acad_plan,
			d.acad_plan_descr,
			d.plan_owner_org,
			d.plan_owner_org_descr,
			d.plan_owner_group_descrshort,
			d.business,
			d.cahnrs_anml,
			d.cahnrs_envr,
			d.cahnrs_econ,
			d.cahnrext,
			d.cas_chem,
			d.cas_crim,
			d.cas_math,
			d.cas_psyc,
			d.cas_biol,
			d.cas_engl,
			d.cas_phys,
			d.cas,
			d.comm,
			d.education,
			d.medicine,
			d.nursing,
			d.pharmacy,
			d.provost,
			d.vcea_bioe,
			d.vcea_cive,
			d.vcea_desn,
			d.vcea_eecs,
			d.vcea_mech,
			d.vcea,
			d.vet_med,
			d.lsamp_stem_flag,
			d.anywhere_stem_flag,
			e.need_snap,
			e.fed_efc,
			e.fed_need,
			f.aid_snap,
			f.total_disb,
			f.total_offer,
			f.total_accept,
			g.best,
			g.bestr,
			g.qvalue,
			g.act_engl,
			g.act_read,
			g.act_math,
			g.sat_erws,
			g.sat_mss,
			g.sat_comp,
			h.ad_dta,
			h.ad_ast,
			i.ap,
			i.rs,
			i.chs,
			i.ib,
			i.aice,
			largest(1, i.ib, i.aice) as IB_AICE,
			j.attendee_alive,
			j.attendee_campus_visit,
			j.attendee_cashe,
			j.attendee_destination,
			j.attendee_experience,
			j.attendee_fcd_pullman,
			j.attendee_fced,
			j.attendee_fcoc,
			j.attendee_fcod,
			j.attendee_group_visit,
			j.attendee_honors_visit,
			j.attendee_imagine_tomorrow,
			j.attendee_imagine_u,
			j.attendee_la_bienvenida,
			j.attendee_lvp_camp,
			j.attendee_oos_destination,
			j.attendee_oos_experience,
			j.attendee_preview,
			j.attendee_preview_jrs,
			j.attendee_shaping,
			j.attendee_top_scholars,
			j.attendee_transfer_day,
			j.attendee_vibes,
			j.attendee_welcome_center,
			j.attendee_any_visitation_ind,
			j.attendee_total_visits,
			k.athlete,
			l.remedial,
			m.min_week_from_term_begin_dt,
			m.max_week_from_term_begin_dt,
			m.count_week_from_term_begin_dt,
			(4.0 - n.avg_difficulty) as avg_difficulty,
			n.avg_pct_withdrawn,
			n.avg_pct_CDFW,
			n.avg_pct_CDF,
			n.avg_pct_DFW,
			n.avg_pct_DF,
			s.fall_lec_count,
			s.fall_lab_count,
			s.spring_lec_count,
			s.spring_lab_count,
			o.fall_lec_contact_hrs,
 			o.fall_lab_contact_hrs,
 			o.spring_lec_contact_hrs,
 			o.spring_lab_contact_hrs,
			o.total_fall_contact_hrs,
			o.total_spring_contact_hrs,
			p.sat_sup_rwc,
			p.sat_sup_ce,
			p.sat_sup_ha,
			p.sat_sup_psda,
			p.sat_sup_ei,
			p.sat_sup_pam,
			p.sat_sup_sec,
			q.camp_addr_indicator,
			q.housing_reshall_indicator,
			q.housing_ssa_indicator,
			q.housing_family_indicator,
			q.afl_reshall_indicator,
			q.afl_ssa_indicator,
			q.afl_family_indicator,
			q.afl_greek_indicator,
			q.afl_greek_life_indicator,
			r.building_id,
			t.race_american_indian,
			t.race_alaska,
			t.race_asian,
			t.race_black,
			t.race_native_hawaiian,
			t.race_white
		from cohort_&cohort_year. as a
		left join new_student_&cohort_year. as b
			on a.emplid = b.emplid
		left join enrolled_&cohort_year. as c
			on a.emplid = c.emplid
 				and a.term_code + 10 = c.cont_term
 		left join plan_&cohort_year. as d
 			on a.emplid = d.emplid
 		left join need_&cohort_year. as e
 			on a.emplid = e.emplid
 				and a.aid_year = e.aid_year
 		left join aid_&cohort_year. as f
 			on a.emplid = f.emplid
 				and a.aid_year = f.aid_year
 		left join exams_&cohort_year. as g
 			on a.emplid = g.emplid
 		left join degrees_&cohort_year. as h
 			on a.emplid = h.emplid
 		left join preparatory_&cohort_year. as i
 			on a.emplid = i.emplid
 		left join visitation_&cohort_year. as j
 			on a.emplid = j.emplid
 		left join athlete_&cohort_year. as k
 			on a.emplid = k.emplid
		left join remedial_&cohort_year. as l
 			on a.emplid = l.emplid
 		left join date_&cohort_year. as m
 			on a.emplid = m.emplid
 		left join coursework_difficulty_&cohort_year. as n
 			on a.emplid = n.emplid
 		left join term_contact_hrs_&cohort_year. as o
 			on a.emplid = o.emplid
 		left join exams_detail_&cohort_year. as p
 			on a.emplid = p.emplid
 		left join housing_&cohort_year. as q
 			on a.emplid = q.emplid
 		left join housing_detail_&cohort_year. as r
 			on a.emplid = r.emplid
 		left join class_count_&cohort_year. as s
 			on a.emplid = s.emplid
 		left join race_detail_&cohort_year. as t
 			on a.emplid = t.emplid
	;quit;
	
	%end;
	
	proc sql;
		create table race_detail_&cohort_year. as
		select 
			a.emplid,
			case when hispc.emplid is not null 	then 'Y'
												else 'N'
												end as race_hispanic,
			case when amind.emplid is not null 	then 'Y'
											   	else 'N'
											   	end as race_american_indian,
			case when alask.emplid is not null 	then 'Y'
											   	else 'N'
											   	end as race_alaska,
			case when asian.emplid is not null 	then 'Y'
											   	else 'N'
											   	end as race_asian,
			case when black.emplid is not null 	then 'Y'
											   	else 'N'
											   	end as race_black,
			case when hawai.emplid is not null 	then 'Y'
											   	else 'N'
											   	end as race_native_hawaiian,
			case when white.emplid is not null 	then 'Y'
											   	else 'N'
											   	end as race_white
		from &adm..fact_u as a
		left join &adm..xd_admit_type as b
			on a.sid_admit_type = b.sid_admit_type
		left join (select distinct e4.emplid from &dsn..student_ethnic_detail as e4
					left join &dsn..xw_ethnic_detail_to_group_vw as xe4
						on e4.ethnic_cd = xe4.ethnic_cd
					where e4.snapshot = 'census'
						and e4.strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
						and xe4.ethnic_group = '4') as asian
			on a.emplid = asian.emplid
		left join (select distinct e2.emplid from &dsn..student_ethnic_detail as e2
					left join &dsn..xw_ethnic_detail_to_group_vw as xe2
						on e2.ethnic_cd = xe2.ethnic_cd
					where e2.snapshot = 'census'
						and e2.strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
						and xe2.ethnic_group = '2') as black
			on a.emplid = black.emplid
		left join (select distinct e7.emplid from &dsn..student_ethnic_detail as e7
					left join &dsn..xw_ethnic_detail_to_group_vw as xe7
						on e7.ethnic_cd = xe7.ethnic_cd
					where e7.snapshot = 'census'
						and e7.strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
						and xe7.ethnic_group = '7') as hawai
			on a.emplid = hawai.emplid
		left join (select distinct e1.emplid from &dsn..student_ethnic_detail as e1
					left join &dsn..xw_ethnic_detail_to_group_vw as xe1
						on e1.ethnic_cd = xe1.ethnic_cd
					where e1.snapshot = 'census'
						and e1.strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
						and xe1.ethnic_group = '1') as white
			on a.emplid = white.emplid
		left join (select distinct e5a.emplid from &dsn..student_ethnic_detail as e5a
					left join &dsn..xw_ethnic_detail_to_group_vw as xe5a
						on e5a.ethnic_cd = xe5a.ethnic_cd
					where e5a.snapshot = 'census' 
						and e5a.strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
						and xe5a.ethnic_group = '5'
						and e5a.ethnic_cd in ('014','016','017','018',
												'935','941','942','943',
												'950','R10','R14')) as alask
			on a.emplid = alask.emplid
		left join (select distinct e5b.emplid from &dsn..student_ethnic_detail as e5b
					left join &dsn..xw_ethnic_detail_to_group_vw as xe5b
						on e5b.ethnic_cd = xe5b.ethnic_cd
					where e5b.snapshot = 'census'
						and e5b.strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
						and xe5b.ethnic_group = '5'
						and e5b.ethnic_cd not in ('014','016','017','018',
													'935','941','942','943',
													'950','R14')) as amind
			on a.emplid = amind.emplid
		left join (select distinct e6.emplid from &dsn..student_ethnic_detail as e6
					left join &dsn..xw_ethnic_detail_to_group_vw as xe6
						on e6.ethnic_cd = xe6.ethnic_cd
					where e6.snapshot = 'census'
						and e6.strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
						and xe6.ethnic_group = '3') as hispc
			on a.emplid = hispc.emplid
		where a.sid_snapshot = (select max(sid_snapshot) as sid_snapshot 
								from &adm..fact_u where strm = (substr(put(%eval(&cohort_year. - &lag_year.), z4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), z4.), 3, 2) || '7'))
			and a.acad_career = 'UGRD' 
			and a.campus = 'PULLM' 
			and a.enrolled = 1
			and b.admit_type in ('FRS','IFR','IPF')
	;quit;
	
	proc sql;
		create table remedial_&cohort_year. as
		select distinct
			emplid,
			case when grading_basis_enrl in ('REM','RMS','RMP') 	then 1
																	else 0
																	end as remedial
		from &dsn..class_registration_vw
		where snapshot = 'census'
			and aid_year = "&cohort_year."
			and grading_basis_enrl in ('REM','RMS','RMP')
		order by emplid
	;quit;
	
	proc sql;
		create table class_registration_&cohort_year. as
		select distinct
			strm,
			emplid,
			class_nbr,
			crse_id,
			strip(subject) || ' ' || strip(catalog_nbr) as subject_catalog_nbr,
			ssr_component
		from acs.subcatnbr_data
	;quit;
	
	proc sql;
		create table class_difficulty_&cohort_year. as
		select distinct
			a.subject_catalog_nbr,
			a.ssr_component,
			coalesce(b.total_grade_A, 0) + coalesce(c.total_grade_A, 0) as total_grade_A,
			(calculated total_grade_A * 4.0) as total_grade_A_GPA,
			coalesce(b.total_grade_A_minus, 0) + coalesce(c.total_grade_A_minus, 0) as total_grade_A_minus,
			(calculated total_grade_A_minus * 3.7) as total_grade_A_minus_GPA,
			coalesce(b.total_grade_B_plus, 0) + coalesce(c.total_grade_B_plus, 0) as total_grade_B_plus,
			(calculated total_grade_B_plus * 3.3) as total_grade_B_plus_GPA,
			coalesce(b.total_grade_B, 0) + coalesce(c.total_grade_B, 0) as total_grade_B,
			(calculated total_grade_B * 3.0) as total_grade_B_GPA,
			coalesce(b.total_grade_B_minus, 0) + coalesce(c.total_grade_B_minus, 0) as total_grade_B_minus,
			(calculated total_grade_B_minus * 2.7) as total_grade_B_minus_GPA,
			coalesce(b.total_grade_C_plus, 0) + coalesce(c.total_grade_C_plus, 0) as total_grade_C_plus,
			(calculated total_grade_C_plus * 2.3) as total_grade_C_plus_GPA,
			coalesce(b.total_grade_C, 0) + coalesce(c.total_grade_C, 0) as total_grade_C,
			(calculated total_grade_C * 2.0) as total_grade_C_GPA,
			coalesce(b.total_grade_C_minus, 0) + coalesce(c.total_grade_C_minus, 0) as total_grade_C_minus,
			(calculated total_grade_C_minus * 1.7) as total_grade_C_minus_GPA,
			coalesce(b.total_grade_D_plus, 0) + coalesce(c.total_grade_D_plus, 0) as total_grade_D_plus,
			(calculated total_grade_D_plus * 1.3) as total_grade_D_plus_GPA,
			coalesce(b.total_grade_D, 0) + coalesce(c.total_grade_D, 0) as total_grade_D,
			(calculated total_grade_D * 1.0) as total_grade_D_GPA,
			coalesce(b.total_grade_F, 0) + coalesce(c.total_grade_F, 0) as total_grade_F,
			coalesce(b.total_withdrawn, 0) + coalesce(c.total_withdrawn, 0) as total_withdrawn,
			(calculated total_grade_A + calculated total_grade_A_minus 
				+ calculated total_grade_B_plus + calculated total_grade_B + calculated total_grade_B_minus
				+ calculated total_grade_C_plus + calculated total_grade_C + calculated total_grade_C_minus
				+ calculated total_grade_D_plus + calculated total_grade_D + calculated total_grade_F) as total_grades,
			(calculated total_grade_A + calculated total_grade_A_minus 
				+ calculated total_grade_B_plus + calculated total_grade_B + calculated total_grade_B_minus
				+ calculated total_grade_C_plus + calculated total_grade_C + calculated total_grade_C_minus
				+ calculated total_grade_D_plus + calculated total_grade_D + calculated total_grade_F + calculated total_withdrawn) as total_students,
			(calculated total_grade_A_GPA + calculated total_grade_A_minus_GPA 
				+ calculated total_grade_B_plus_GPA + calculated total_grade_B_GPA + calculated total_grade_B_minus_GPA
				+ calculated total_grade_C_plus_GPA + calculated total_grade_C_GPA + calculated total_grade_C_minus_GPA
				+ calculated total_grade_D_plus_GPA + calculated total_grade_D_GPA) as total_grades_GPA,
			(calculated total_grades_GPA / calculated total_grades) as class_average,
			(calculated total_withdrawn / calculated total_students) as pct_withdrawn,
			(calculated total_grade_C_minus + calculated total_grade_D_plus + calculated total_grade_D 
				+ calculated total_grade_F + calculated total_withdrawn) as CDFW,
			(calculated CDFW / calculated total_students) as pct_CDFW,
			(calculated total_grade_C_minus + calculated total_grade_D_plus + calculated total_grade_D 
				+ calculated total_grade_F) as CDF,
			(calculated CDF / calculated total_students) as pct_CDF,
			(calculated total_grade_D_plus + calculated total_grade_D + calculated total_grade_F 
				+ calculated total_withdrawn) as DFW,
			(calculated DFW / calculated total_students) as pct_DFW,
			(calculated total_grade_D_plus + calculated total_grade_D + calculated total_grade_F) as DF,
			(calculated DF / calculated total_students) as pct_DF
		from &dsn..class_vw as a
		left join (select distinct 
						subject_catalog_nbr,
						ssr_component,
						sum(total_grade_A) as total_grade_A,
						sum(total_grade_A_minus) as total_grade_A_minus,
						sum(total_grade_B_plus) as total_grade_B_plus,
						sum(total_grade_B) as total_grade_B,
						sum(total_grade_B_minus) as total_grade_B_minus,
						sum(total_grade_C_plus) as total_grade_C_plus,
						sum(total_grade_C) as total_grade_C,
						sum(total_grade_C_minus) as total_grade_C_minus,
						sum(total_grade_D_plus) as total_grade_D_plus,
						sum(total_grade_D) as total_grade_D,
						sum(total_grade_F) as total_grade_F,
						sum(total_withdrawn) as total_withdrawn
					from &dsn..class_vw
					where snapshot = 'eot'
						and full_acad_year = put(%eval(&cohort_year. - &lag_year.), 4.)
						and ssr_component = 'LEC'
					group by subject_catalog_nbr) as b
			on a.subject_catalog_nbr = b.subject_catalog_nbr
				and a.ssr_component = b.ssr_component
		left join (select distinct 
						subject_catalog_nbr,
						ssr_component,
						sum(total_grade_A) as total_grade_A,
						sum(total_grade_A_minus) as total_grade_A_minus,
						sum(total_grade_B_plus) as total_grade_B_plus,
						sum(total_grade_B) as total_grade_B,
						sum(total_grade_B_minus) as total_grade_B_minus,
						sum(total_grade_C_plus) as total_grade_C_plus,
						sum(total_grade_C) as total_grade_C,
						sum(total_grade_C_minus) as total_grade_C_minus,
						sum(total_grade_D_plus) as total_grade_D_plus,
						sum(total_grade_D) as total_grade_D,
						sum(total_grade_F) as total_grade_F,
						sum(total_withdrawn) as total_withdrawn
					from &dsn..class_vw
					where snapshot = 'eot'
						and full_acad_year = put(%eval(&cohort_year. - &lag_year.), 4.)
						and ssr_component = 'LAB'
					group by subject_catalog_nbr) as c
			on a.subject_catalog_nbr = c.subject_catalog_nbr
				and a.ssr_component = c.ssr_component
		where a.snapshot = 'census'
			and a.full_acad_year = "&cohort_year."
			and a.ssr_component in ('LEC','LAB')
		group by a.subject_catalog_nbr
		order by a.subject_catalog_nbr
	;quit;
	
	proc sql;
		create table class_count_&cohort_year. as
		select distinct
			a.emplid,
			count(b.class_nbr) as fall_lec_count,
			count(c.class_nbr) as fall_lab_count,
			count(d.class_nbr) as spring_lec_count,
			count(e.class_nbr) as spring_lab_count,
			coalesce(calculated fall_lec_count, 0) + coalesce(calculated spring_lec_count, 0) as total_lec_count,
			coalesce(calculated fall_lab_count, 0) + coalesce(calculated spring_lab_count, 0) as total_lab_count
		from class_registration_&cohort_year. as a
		left join (select distinct emplid, 
						class_nbr
					from class_registration_&cohort_year.
					where substr(strm,4,1) = '7'
						and ssr_component = 'LEC') as b
			on a.emplid = b.emplid
				and a.class_nbr = b.class_nbr
		left join (select distinct emplid, 
						class_nbr
					from class_registration_&cohort_year.
					where substr(strm,4,1) = '7'
						and ssr_component = 'LAB') as c
			on a.emplid = c.emplid
				and a.class_nbr = c.class_nbr
		left join (select distinct emplid, 
						class_nbr
					from class_registration_&cohort_year.
					where substr(strm,4,1) = '3'
						and ssr_component = 'LEC') as d
			on a.emplid = d.emplid
				and a.class_nbr = d.class_nbr
		left join (select distinct emplid, 
						class_nbr
					from class_registration_&cohort_year.
					where substr(strm,4,1) = '3'
						and ssr_component = 'LAB') as e
			on a.emplid = e.emplid
				and a.class_nbr = e.class_nbr
		group by a.emplid
	;quit;
	
	proc sql;
		create table coursework_difficulty_&cohort_year. as
		select distinct
			a.emplid,
			avg(b.class_average) as avg_difficulty,
			avg(b.pct_withdrawn) as avg_pct_withdrawn,
			avg(b.pct_CDFW) as avg_pct_CDFW,
			avg(b.pct_CDF) as avg_pct_CDF,
			avg(b.pct_DFW) as avg_pct_DFW,
			avg(b.pct_DF) as avg_pct_DF
		from class_registration_&cohort_year. as a
		left join class_difficulty_&cohort_year. as b
			on a.subject_catalog_nbr = b.subject_catalog_nbr
		group by a.emplid
	;quit;

	proc sql;
		create table term_contact_hrs_&cohort_year. as
		select distinct
			a.emplid,
			sum(b.lec_contact_hrs) as fall_lec_contact_hrs,
			sum(c.lab_contact_hrs) as fall_lab_contact_hrs,
			sum(d.lec_contact_hrs) as spring_lec_contact_hrs,
			sum(e.lab_contact_hrs) as spring_lab_contact_hrs,
			coalesce(calculated fall_lec_contact_hrs, 0) + coalesce(calculated fall_lab_contact_hrs, 0) as total_fall_contact_hrs,
			coalesce(calculated spring_lec_contact_hrs, 0) + coalesce(calculated spring_lab_contact_hrs, 0) as total_spring_contact_hrs
		from class_registration_&cohort_year. as a
		left join (select distinct
						subject_catalog_nbr,
						max(term_contact_hrs) as lec_contact_hrs,
						ssr_component
					from &dsn..class_vw
					where snapshot = 'census'
						and full_acad_year = put(%eval(&cohort_year.), 4.)
						and substr(strm,4,1) = '7' 
						and ssr_component = 'LEC'
					group by subject_catalog_nbr) as b
			on a.subject_catalog_nbr = b.subject_catalog_nbr
				and a.ssr_component = b.ssr_component
				and substr(a.strm,4,1) = '7'
		left join (select distinct
						subject_catalog_nbr,
						max(term_contact_hrs) as lab_contact_hrs,
						ssr_component
					from &dsn..class_vw
					where snapshot = 'census'
						and full_acad_year = put(%eval(&cohort_year.), 4.)
						and substr(strm,4,1) = '7' 
						and ssr_component = 'LAB'
					group by subject_catalog_nbr) as c
			on a.subject_catalog_nbr = c.subject_catalog_nbr
				and a.ssr_component = c.ssr_component
				and substr(a.strm,4,1) = '7'
		left join (select distinct
						subject_catalog_nbr,
						max(term_contact_hrs) as lec_contact_hrs,
						ssr_component
					from &dsn..class_vw
					where snapshot = 'census'
						and full_acad_year = put(%eval(&cohort_year.), 4.)
						and substr(strm,4,1) = '3' 
						and ssr_component = 'LEC'
					group by subject_catalog_nbr) as d
			on a.subject_catalog_nbr = d.subject_catalog_nbr
				and a.ssr_component = d.ssr_component
				and substr(a.strm,4,1) = '3'
		left join (select distinct
						subject_catalog_nbr,
						max(term_contact_hrs) as lab_contact_hrs,
						ssr_component
					from &dsn..class_vw
					where snapshot = 'census'
						and full_acad_year = put(%eval(&cohort_year.), 4.)
						and substr(strm,4,1) = '3' 
						and ssr_component = 'LAB'
					group by subject_catalog_nbr) as e
			on a.subject_catalog_nbr = e.subject_catalog_nbr
				and a.ssr_component = e.ssr_component
				and substr(a.strm,4,1) = '3'
		group by a.emplid
	;quit;
	
	proc sql;
		create table exams_&cohort_year. as 
		select distinct
			emplid,
			max(case when test_component = 'MSS'	then score
													else .
													end) as sat_mss,
			max(case when test_component = 'ERWS'		then score
													else .
													end) as sat_erws
		from &adm..UGRD_student_test_comp
		where snap_date = (select max(snap_date) as snap_date 
							from &adm..UGRD_student_test_comp 
							where strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7') 
			and strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
			and test_component in ('MSS','ERWS')
		group by emplid
		order by emplid
	;quit;
	
	proc sql;
		create table dataset_&cohort_year. as
		select distinct 
			a.*,
			case when a.sex = 'M' then 1 
					else 0
			end as male,
			b.*,
			case when b.WA_residency = 'RES' then 1
				else 0
			end as resident,
			case when b.adm_parent1_highest_educ_lvl in ('B','C','D','E','F') then '< bach'
				when b.adm_parent1_highest_educ_lvl = 'G' then 'bach'
				when b.adm_parent1_highest_educ_lvl in ('H','I','J','K','L') then '> bach'
					else 'missing'
			end as parent1_highest_educ_lvl,
			case when b.adm_parent2_highest_educ_lvl in ('B','C','D','E','F') then '< bach'
				when b.adm_parent2_highest_educ_lvl = 'G' then 'bach'
				when b.adm_parent2_highest_educ_lvl in ('H','I','J','K','L') then '> bach'
					else 'missing'
			end as parent2_highest_educ_lvl,
			d.*,
			case when d.ipeds_ethnic_group in ('2', '3', '5', '7', 'Z') then 1 
				else 0
			end as underrep_minority,
			substr(e.ext_org_postal,1,5) as targetid,
			f.distance,
			g.median_inc,
			g.gini_indx,
			h.pvrt_total/h.pvrt_base as pvrt_rate,
			i.educ_total/i.educ_base as educ_rate,
			j.pop/(k.area*3.861E-7) as pop_dens,
			l.median_value,
			m.race_blk/m.race_tot as pct_blk,
			m.race_ai/m.race_tot as pct_ai,
			m.race_asn/m.race_tot as pct_asn,
			m.race_hawi/m.race_tot as pct_hawi,
			m.race_oth/m.race_tot as pct_oth,
			m.race_two/m.race_tot as pct_two,
			(m.race_blk + m.race_ai + m.race_asn + m.race_hawi + m.race_oth + m.race_two)/m.race_tot as pct_non,
			n.ethnic_hisp/n.ethnic_tot as pct_hisp,
			case when o.locale = '11' then 1 else 0 end as city_large,
			case when o.locale = '12' then 1 else 0 end as city_mid,
			case when o.locale = '13' then 1 else 0 end as city_small,
			case when o.locale = '21' then 1 else 0 end as suburb_large,
			case when o.locale = '22' then 1 else 0 end as suburb_mid,
			case when o.locale = '23' then 1 else 0 end as suburb_small,
			case when o.locale = '31' then 1 else 0 end as town_fringe,
			case when o.locale = '32' then 1 else 0 end as town_distant,
			case when o.locale = '33' then 1 else 0 end as town_remote,
			case when o.locale = '41' then 1 else 0 end as rural_fringe,
			case when o.locale = '42' then 1 else 0 end as rural_distant,
			case when o.locale = '43' then 1 else 0 end as rural_remote,
			p.remedial,
			(4.0 - q.avg_difficulty) as avg_difficulty,
			q.avg_pct_withdrawn,
			q.avg_pct_CDFW,
			q.avg_pct_CDF,
			q.avg_pct_DFW,
			q.avg_pct_DF,
			u.fall_lec_count,
			u.fall_lab_count,
			u.spring_lec_count,
			u.spring_lab_count,
 			r.fall_lec_contact_hrs,
 			r.fall_lab_contact_hrs,
 			r.spring_lec_contact_hrs,
 			r.spring_lab_contact_hrs,
			r.total_fall_contact_hrs,
			r.total_spring_contact_hrs,
			s.fed_need,
			s.total_offer,
			t.sat_mss,
			t.sat_erws,
			v.race_american_indian,
			v.race_alaska,
			v.race_asian,
			v.race_black,
			v.race_native_hawaiian,
			v.race_white
		from &adm..fact_u as a
		left join &adm..xd_person_demo as b
			on a.sid_per_demo = b.sid_per_demo
		left join &adm..xd_admit_type as c
			on a.sid_admit_type = c.sid_admit_type
		left join &adm..xd_ipeds_ethnic_group as d
			on a.sid_ipeds_ethnic_group = d.sid_ipeds_ethnic_group
		left join &adm..xd_school as e
			on a.sid_ext_org_id = e.sid_ext_org_id
		left join acs.distance as f
			on substr(e.ext_org_postal,1,5) = f.targetid
		left join acs.acs_income_%eval(&cohort_year. - &acs_lag.) as g
			on substr(e.ext_org_postal,1,5) = g.geoid
		left join acs.acs_poverty_%eval(&cohort_year. - &acs_lag.) as h
			on substr(e.ext_org_postal,1,5) = h.geoid
		left join acs.acs_education_%eval(&cohort_year. - &acs_lag.) as i
			on substr(e.ext_org_postal,1,5) = i.geoid
		left join acs.acs_demo_%eval(&cohort_year. - &acs_lag.) as j
			on substr(e.ext_org_postal,1,5) = j.geoid
		left join acs.acs_area_%eval(&cohort_year. - &acs_lag.) as k
			on substr(e.ext_org_postal,1,5) = k.geoid
		left join acs.acs_housing_%eval(&cohort_year. - &acs_lag.) as l
			on substr(e.ext_org_postal,1,5) = l.geoid
		left join acs.acs_race_%eval(&cohort_year. - &acs_lag.) as m
			on substr(e.ext_org_postal,1,5) = m.geoid
		left join acs.acs_ethnicity_%eval(&cohort_year. - &acs_lag.) as n
			on substr(e.ext_org_postal,1,5) = n.geoid
		left join acs.edge_locale14_zcta_table as o
			on substr(e.ext_org_postal,1,5) = o.zcta5ce10
		left join remedial_&cohort_year. as p
			on a.emplid = p.emplid
 		left join coursework_difficulty_&cohort_year. as q
 			on a.emplid = q.emplid
 		left join term_contact_hrs_&cohort_year. as r
 			on a.emplid = r.emplid
 		left join (select distinct emplid, 
 								fed_need, 
 								total_offer 
 						from acs.finaid_data
 						where aid_year = "&cohort_year." group by emplid) as s
 			on a.emplid = s.emplid
 		left join exams_&cohort_year. as t
 			on a.emplid = t.emplid
 		left join class_count_&cohort_year. as u
 			on a.emplid = u.emplid
 		left join race_detail_&cohort_year. as v
 			on a.emplid = v.emplid
		where a.sid_snapshot = (select max(sid_snapshot) as sid_snapshot 
								from &adm..fact_u where strm = (substr(put(%eval(&cohort_year. - &lag_year.), z4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), z4.), 3, 2) || '7'))
			and a.acad_career = 'UGRD' 
			and a.campus = 'PULLM' 
			and a.enrolled = 1
			and c.admit_type in ('FRS','IFR','IPF')
	;quit;
	
%mend loop;
""")

print('Done\n')

#%%
# Run SAS macro program to prepare data from admissions
print('Run SAS macro program...')
start = time.perf_counter()

sas_log = sas.submit("""
%loop;
""")

HTML(sas_log['LOG'])

stop = time.perf_counter()
print(f'Done in {stop - start:.2f} seconds\n')

#%%
# Prepare data
print('Prepare data...')

sas.submit("""
data full_set;
	set dataset_&start_cohort.-dataset_%eval(&end_cohort. + &lag_year.);
	if enrl_ind = . then enrl_ind = 0;
	if ad_dta = . then ad_dta = 0;
	if ad_ast = . then ad_ast = 0;
	if ap = . then ap = 0;
	if rs = . then rs = 0;
	if chs = . then chs = 0;
	if ib = . then ib = 0;
	if aice = . then aice = 0;
	if ib_aice = . then ib_aice = 0;
	if athlete = . then athlete = 0;
	if fed_efc = . then fed_efc = 0;
	if fed_need = . then fed_need = 0;
	if total_disb = . then total_disb = 0;
	if total_offer = . then total_offer = 0;
	if total_accept = . then total_accept = 0;	
	if remedial = . then remedial = 0;
	if sat_mss = . then sat_mss = 0;
	if sat_erws = . then sat_erws = 0;
	if last_sch_proprietorship = '' then last_sch_proprietorship = 'UNKN';
	if ipeds_ethnic_group_descrshort = '' then ipeds_ethnic_group_descrshort = 'NS';
	if avg_pct_withdrawn = . then avg_pct_withdrawn = 0;
	if avg_pct_CDFW = . then avg_pct_CDFW = 0;
	if avg_pct_CDF = . then avg_pct_CDF = 0;
	if avg_pct_DFW = . then avg_pct_DFW = 0;
	if avg_pct_DF = . then avg_pct_DF = 0;
	if avg_difficulty = . then avg_difficulty = 0;
	if fall_lec_count = . then fall_lec_count = 0;
	if fall_lab_count = . then fall_lab_count = 0;
	if spring_lec_count = . then spring_lec_count = 0;
	if spring_lab_count = . then spring_lab_count = 0;
	if fall_lec_contact_hrs = . then fall_lec_contact_hrs = 0;
 	if fall_lab_contact_hrs = . then fall_lab_contact_hrs = 0;
 	if spring_lec_contact_hrs = . then spring_lec_contact_hrs = 0;
 	if spring_lab_contact_hrs = . then spring_lab_contact_hrs = 0;
	if total_fall_contact_hrs = . then total_fall_contact_hrs = 0;
	if total_spring_contact_hrs = . then total_spring_contact_hrs = 0;
	if camp_addr_indicator ^= 'Y' then camp_addr_indicator = 'N';
	if housing_reshall_indicator ^= 'Y' then housing_reshall_indicator = 'N';
	if housing_ssa_indicator ^= 'Y' then housing_ssa_indicator = 'N';
	if housing_family_indicator ^= 'Y' then housing_family_indicator = 'N';
	if afl_reshall_indicator ^= 'Y' then afl_reshall_indicator = 'N';
	if afl_ssa_indicator ^= 'Y' then afl_ssa_indicator = 'N';
	if afl_family_indicator ^= 'Y' then afl_family_indicator = 'N';
	if afl_greek_indicator ^= 'Y' then afl_greek_indicator = 'N';
	if afl_greek_life_indicator ^= 'Y' then afl_greek_life_indicator = 'N';
	unmet_need_disb = fed_need - total_disb;
	unmet_need_acpt = fed_need - total_accept;
	unmet_need_ofr = fed_need - total_offer;
	if unmet_need_ofr < 0 then unmet_need_ofr = 0;
run;

data training_set;
	set dataset_&start_cohort.-dataset_&end_cohort.;
	if enrl_ind = . then enrl_ind = 0;
	if ad_dta = . then ad_dta = 0;
	if ad_ast = . then ad_ast = 0;
	if ap = . then ap = 0;
	if rs = . then rs = 0;
	if chs = . then chs = 0;
	if ib = . then ib = 0;
	if aice = . then aice = 0;
	if ib_aice = . then ib_aice = 0;	
	if athlete = . then athlete = 0;
	if fed_efc = . then fed_efc = 0;
	if fed_need = . then fed_need = 0;
	if total_disb = . then total_disb = 0;
	if total_offer = . then total_offer = 0;
	if total_accept = . then total_accept = 0;
	if remedial = . then remedial = 0;
	if sat_mss = . then sat_mss = 0;
	if sat_erws = . then sat_erws = 0;
	if last_sch_proprietorship = '' then last_sch_proprietorship = 'UNKN';
	if ipeds_ethnic_group_descrshort = '' then ipeds_ethnic_group_descrshort = 'NS';
	if avg_pct_withdrawn = . then avg_pct_withdrawn = 0;
	if avg_pct_CDFW = . then avg_pct_CDFW = 0;
	if avg_pct_CDF = . then avg_pct_CDF = 0;
	if avg_pct_DFW = . then avg_pct_DFW = 0;
	if avg_pct_DF = . then avg_pct_DF = 0;
	if avg_difficulty = . then avg_difficulty = 0;
	if fall_lec_count = . then fall_lec_count = 0;
	if fall_lab_count = . then fall_lab_count = 0;
	if spring_lec_count = . then spring_lec_count = 0;
	if spring_lab_count = . then spring_lab_count = 0;
	if fall_lec_contact_hrs = . then fall_lec_contact_hrs = 0;
 	if fall_lab_contact_hrs = . then fall_lab_contact_hrs = 0;
 	if spring_lec_contact_hrs = . then spring_lec_contact_hrs = 0;
 	if spring_lab_contact_hrs = . then spring_lab_contact_hrs = 0;
	if total_fall_contact_hrs = . then total_fall_contact_hrs = 0;
	if total_spring_contact_hrs = . then total_spring_contact_hrs = 0;
	if camp_addr_indicator ^= 'Y' then camp_addr_indicator = 'N';
	if housing_reshall_indicator ^= 'Y' then housing_reshall_indicator = 'N';
	if housing_ssa_indicator ^= 'Y' then housing_ssa_indicator = 'N';
	if housing_family_indicator ^= 'Y' then housing_family_indicator = 'N';
	if afl_reshall_indicator ^= 'Y' then afl_reshall_indicator = 'N';
	if afl_ssa_indicator ^= 'Y' then afl_ssa_indicator = 'N';
	if afl_family_indicator ^= 'Y' then afl_family_indicator = 'N';
	if afl_greek_indicator ^= 'Y' then afl_greek_indicator = 'N';
	if afl_greek_life_indicator ^= 'Y' then afl_greek_life_indicator = 'N';
	unmet_need_disb = fed_need - total_disb;
	unmet_need_acpt = fed_need - total_accept;
	unmet_need_ofr = fed_need - total_offer;
	if unmet_need_ofr < 0 then unmet_need_ofr = 0;
run;

data testing_set;
	set dataset_%eval(&end_cohort. + &lag_year.);
	if enrl_ind = . then enrl_ind = 0;
	if ad_dta = . then ad_dta = 0;
	if ad_ast = . then ad_ast = 0;
	if ap = . then ap = 0;
	if rs = . then rs = 0;
	if chs = . then chs = 0;
	if ib = . then ib = 0;
	if aice = . then aice = 0;
	if ib_aice = . then ib_aice = 0;
	if athlete = . then athlete = 0;
	if fed_efc = . then fed_efc = 0;
	if fed_need = . then fed_need = 0;
	if total_disb = . then total_disb = 0;
	if total_offer = . then total_offer = 0;
	if total_accept = . then total_accept = 0;
	if remedial = . then remedial = 0;
	if sat_mss = . then sat_mss = 0;
	if sat_erws = . then sat_erws = 0;
	if last_sch_proprietorship = '' then last_sch_proprietorship = 'UNKN';
	if ipeds_ethnic_group_descrshort = '' then ipeds_ethnic_group_descrshort = 'NS';
	if avg_pct_withdrawn = . then avg_pct_withdrawn = 0;
	if avg_pct_CDFW = . then avg_pct_CDFW = 0;
	if avg_pct_CDF = . then avg_pct_CDF = 0;
	if avg_pct_DFW = . then avg_pct_DFW = 0;
	if avg_pct_DF = . then avg_pct_DF = 0;
	if avg_difficulty = . then avg_difficulty = 0;
	if fall_lec_count = . then fall_lec_count = 0;
	if fall_lab_count = . then fall_lab_count = 0;
	if spring_lec_count = . then spring_lec_count = 0;
	if spring_lab_count = . then spring_lab_count = 0;
	if fall_lec_contact_hrs = . then fall_lec_contact_hrs = 0;
 	if fall_lab_contact_hrs = . then fall_lab_contact_hrs = 0;
 	if spring_lec_contact_hrs = . then spring_lec_contact_hrs = 0;
 	if spring_lab_contact_hrs = . then spring_lab_contact_hrs = 0;
	if total_fall_contact_hrs = . then total_fall_contact_hrs = 0;
	if total_spring_contact_hrs = . then total_spring_contact_hrs = 0;
	if camp_addr_indicator ^= 'Y' then camp_addr_indicator = 'N';
	if housing_reshall_indicator ^= 'Y' then housing_reshall_indicator = 'N';
	if housing_ssa_indicator ^= 'Y' then housing_ssa_indicator = 'N';
	if housing_family_indicator ^= 'Y' then housing_family_indicator = 'N';
	if afl_reshall_indicator ^= 'Y' then afl_reshall_indicator = 'N';
	if afl_ssa_indicator ^= 'Y' then afl_ssa_indicator = 'N';
	if afl_family_indicator ^= 'Y' then afl_family_indicator = 'N';
	if afl_greek_indicator ^= 'Y' then afl_greek_indicator = 'N';
	if afl_greek_life_indicator ^= 'Y' then afl_greek_life_indicator = 'N';
	unmet_need_disb = fed_need - total_disb;
	unmet_need_acpt = fed_need - total_accept;
	unmet_need_ofr = fed_need - total_offer;
	if unmet_need_ofr < 0 then unmet_need_ofr = 0;
run;
""")

print('Done\n')

#%%
# Export data from SAS
print('Export data from SAS...')

sas_log = sas.submit("""
filename full \"Z:\\Nathan\\Models\\student_risk\\datasets\\full_set.csv\" encoding="utf-8";

proc export data=full_set outfile=full dbms=csv replace;
run;

filename training \"Z:\\Nathan\\Models\\student_risk\\datasets\\training_set.csv\" encoding="utf-8";

proc export data=training_set outfile=training dbms=csv replace;
run;

filename testing \"Z:\\Nathan\\Models\\student_risk\\datasets\\testing_set.csv" encoding="utf-8";

proc export data=testing_set outfile=testing dbms=csv replace;
run;
""")

HTML(sas_log['LOG'])

print('Done\n')

#%%
# End SAS session
sas.endsas()

#%%
# Import pre-split data for scikit-learn
training_set = pd.read_csv('Z:\\Nathan\\Models\\student_risk\\datasets\\training_set.csv', encoding='utf-8', low_memory=False)
testing_set = pd.read_csv('Z:\\Nathan\\Models\\student_risk\\datasets\\testing_set.csv', encoding='utf-8', low_memory=False)

#%%
# Prepare dataframes
print('\nPrepare dataframes and preprocess data...')

logit_df = training_set[[
                        'enrl_ind', 
                        # 'acad_year',
                        # 'age_group', 
                        # 'age',
                        'male',
                        # 'min_week_from_term_begin_dt',
                        # 'max_week_from_term_begin_dt',
                        'count_week_from_term_begin_dt',
                        # 'marital_status',
                        # 'Distance',
                        # 'pop_dens',
                        'underrep_minority', 
                        # 'ipeds_ethnic_group_descrshort',
                        'pell_eligibility_ind', 
                        # 'pell_recipient_ind',
                        'first_gen_flag', 
                        # 'LSAMP_STEM_Flag',
                        # 'anywhere_STEM_Flag',
                        # 'afl_greek_indicator',
                        'high_school_gpa',
                        # 'awe_instrument',
                        # 'cdi_instrument',
                        'avg_difficulty',
                        'avg_pct_withdrawn',
                        # 'avg_pct_CDFW',
                        'avg_pct_CDF',
                        # 'avg_pct_DFW',
                        # 'avg_pct_DF',
						'fall_lec_count',
						'fall_lab_count',
                        # 'fall_lec_contact_hrs',
                        # 'fall_lab_contact_hrs',
						# 'spring_lec_count',
						# 'spring_lab_count',
                        # 'spring_lec_contact_hrs',
                        # 'spring_lab_contact_hrs',
						'total_fall_contact_hrs',
                        'cum_adj_transfer_hours',
                        'resident',
                        # 'father_wsu_flag',
                        # 'mother_wsu_flag',
                        'parent1_highest_educ_lvl',
                        'parent2_highest_educ_lvl',
                        # 'citizenship_country',
                        'gini_indx',
                        # 'pvrt_rate',
                        'median_inc',
                        # 'median_value',
                        # 'educ_rate',
                        'pct_blk',
                        'pct_ai',
                        # 'pct_asn',
                        'pct_hawi',
                        # 'pct_oth',
                        'pct_two',
                        # 'pct_non',
                        'pct_hisp',
                        'city_large',
                        'city_mid',
                        'city_small',
                        'suburb_large',
                        'suburb_mid',
                        'suburb_small',
                        # 'town_fringe',
                        # 'town_distant',
                        # 'town_remote',
                        # 'rural_fringe',
                        # 'rural_distant',
                        # 'rural_remote',
                        # 'AD_DTA',
                        # 'AD_AST',
                        # 'AP',
                        # 'RS',
                        # 'CHS',
                        # 'IB',
                        # 'AICE',
                        # 'IB_AICE', 
                        # 'term_credit_hours',
                        # 'athlete',
                        'remedial',
                        # 'ACAD_PLAN',
                        # 'plan_owner_org',
                        # 'business',
                        # 'cahnrs_anml',
                        # 'cahnrs_envr',
                        # 'cahnrs_econ',
                        # 'cahnrext',
                        # 'cas_chem',
                        # 'cas_crim',
                        # 'cas_math',
                        # 'cas_psyc',
                        # 'cas_biol',
                        # 'cas_engl',
                        # 'cas_phys',
                        # 'cas',
                        # 'comm',
                        # 'education',
                        # 'medicine',
                        # 'nursing',
                        # 'pharmacy',
                        # 'provost',
                        # 'vcea_bioe',
                        # 'vcea_cive',
                        # 'vcea_desn',
                        # 'vcea_eecs',
                        # 'vcea_mech',
                        # 'vcea',
                        # 'vet_med',
                        # 'last_sch_proprietorship',
                        # 'sat_erws',
                        # 'sat_mss',
                        # 'sat_comp',
                        # 'attendee_alive',
                        # 'attendee_campus_visit',
                        # 'attendee_cashe',
                        # 'attendee_destination',
                        # 'attendee_experience',
                        # 'attendee_fcd_pullman',
                        # 'attendee_fced',
                        # 'attendee_fcoc',
                        # 'attendee_fcod',
                        # 'attendee_group_visit',
                        # 'attendee_honors_visit',
                        # 'attendee_imagine_tomorrow',
                        # 'attendee_imagine_u',
                        # 'attendee_la_bienvenida',
                        # 'attendee_lvp_camp',
                        # 'attendee_oos_destination',
                        # 'attendee_oos_experience',
                        # 'attendee_preview',
                        # 'attendee_preview_jrs',
                        # 'attendee_shaping',
                        # 'attendee_top_scholars',
                        # 'attendee_transfer_day',
                        # 'attendee_vibes',
                        # 'attendee_welcome_center',
                        # 'attendee_any_visitation_ind',
                        # 'attendee_total_visits',
                        # 'qvalue',
                        # 'fed_efc',
                        # 'fed_need',
                        'unmet_need_ofr'
                        ]].dropna()

training_set = training_set[[
                            'emplid',
                            'enrl_ind', 
                        	# 'acad_year',
							# 'age_group', 
							# 'age',
							'male',
							# 'min_week_from_term_begin_dt',
							# 'max_week_from_term_begin_dt',
							'count_week_from_term_begin_dt',
							# 'marital_status',
							# 'Distance',
							# 'pop_dens',
							'underrep_minority', 
							# 'ipeds_ethnic_group_descrshort',
							'pell_eligibility_ind', 
							# 'pell_recipient_ind',
							'first_gen_flag', 
							# 'LSAMP_STEM_Flag',
							# 'anywhere_STEM_Flag',
							# 'afl_greek_indicator',
							'high_school_gpa',
							# 'awe_instrument',
							# 'cdi_instrument',
							'avg_difficulty',
							'avg_pct_withdrawn',
							# 'avg_pct_CDFW',
							'avg_pct_CDF',
							# 'avg_pct_DFW',
							# 'avg_pct_DF',
							'fall_lec_count',
							'fall_lab_count',
							# 'fall_lec_contact_hrs',
                        	# 'fall_lab_contact_hrs',
							# 'spring_lec_count',
							# 'spring_lab_count',
							# 'spring_lec_contact_hrs',
							# 'spring_lab_contact_hrs',
							'total_fall_contact_hrs',
							'cum_adj_transfer_hours',
							'resident',
							# 'father_wsu_flag',
							# 'mother_wsu_flag',
							'parent1_highest_educ_lvl',
							'parent2_highest_educ_lvl',
							# 'citizenship_country',
							'gini_indx',
							# 'pvrt_rate',
							'median_inc',
							# 'median_value',
							# 'educ_rate',
							'pct_blk',
							'pct_ai',
							# 'pct_asn',
							'pct_hawi',
							# 'pct_oth',
							'pct_two',
							# 'pct_non',
							'pct_hisp',
							'city_large',
							'city_mid',
							'city_small',
							'suburb_large',
							'suburb_mid',
							'suburb_small',
							# 'town_fringe',
							# 'town_distant',
							# 'town_remote',
							# 'rural_fringe',
							# 'rural_distant',
							# 'rural_remote',
							# 'AD_DTA',
							# 'AD_AST',
							# 'AP',
							# 'RS',
							# 'CHS',
							# 'IB',
							# 'AICE',
							# 'IB_AICE', 
							# 'term_credit_hours',
							# 'athlete',
							'remedial',
							# 'ACAD_PLAN',
							# 'plan_owner_org',
							# 'business',
							# 'cahnrs_anml',
							# 'cahnrs_envr',
							# 'cahnrs_econ',
							# 'cahnrext',
							# 'cas_chem',
							# 'cas_crim',
							# 'cas_math',
							# 'cas_psyc',
							# 'cas_biol',
							# 'cas_engl',
							# 'cas_phys',
							# 'cas',
							# 'comm',
							# 'education',
							# 'medicine',
							# 'nursing',
							# 'pharmacy',
							# 'provost',
							# 'vcea_bioe',
							# 'vcea_cive',
							# 'vcea_desn',
							# 'vcea_eecs',
							# 'vcea_mech',
							# 'vcea',
							# 'vet_med',
							# 'last_sch_proprietorship',
							# 'sat_erws',
							# 'sat_mss',
							# 'sat_comp',
							# 'attendee_alive',
							# 'attendee_campus_visit',
							# 'attendee_cashe',
							# 'attendee_destination',
							# 'attendee_experience',
							# 'attendee_fcd_pullman',
							# 'attendee_fced',
							# 'attendee_fcoc',
							# 'attendee_fcod',
							# 'attendee_group_visit',
							# 'attendee_honors_visit',
							# 'attendee_imagine_tomorrow',
							# 'attendee_imagine_u',
							# 'attendee_la_bienvenida',
							# 'attendee_lvp_camp',
							# 'attendee_oos_destination',
							# 'attendee_oos_experience',
							# 'attendee_preview',
							# 'attendee_preview_jrs',
							# 'attendee_shaping',
							# 'attendee_top_scholars',
							# 'attendee_transfer_day',
							# 'attendee_vibes',
							# 'attendee_welcome_center',
							# 'attendee_any_visitation_ind',
							# 'attendee_total_visits',
							# 'qvalue',
							# 'fed_efc',
							# 'fed_need',
							'unmet_need_ofr'
                            ]].dropna()

testing_set = testing_set[[
                            'emplid',
							'ENRL_IND',
                            # 'acad_year',
							# 'age_group', 
							# 'age',
							'male',
							# 'min_week_from_term_begin_dt',
							# 'max_week_from_term_begin_dt',
							'count_week_from_term_begin_dt',
							# 'marital_status',
							# 'Distance',
							# 'pop_dens',
							'underrep_minority', 
							# 'ipeds_ethnic_group_descrshort',
							'pell_eligibility_ind', 
							# 'pell_recipient_ind',
							'first_gen_flag', 
							# 'LSAMP_STEM_Flag',
							# 'anywhere_STEM_Flag',
							# 'afl_greek_indicator',
							'high_school_gpa',
							# 'awe_instrument',
							# 'cdi_instrument',
							'avg_difficulty',
							'avg_pct_withdrawn',
							# 'avg_pct_CDFW',
							'avg_pct_CDF',
							# 'avg_pct_DFW',
							# 'avg_pct_DF',
							'fall_lec_count',
							'fall_lab_count',
							# 'fall_lec_contact_hrs',
                        	# 'fall_lab_contact_hrs',
							# 'spring_lec_count',
							# 'spring_lab_count',
							# 'spring_lec_contact_hrs',
							# 'spring_lab_contact_hrs',
							'total_fall_contact_hrs',
							'cum_adj_transfer_hours',
							'resident',
							# 'father_wsu_flag',
							# 'mother_wsu_flag',
							'parent1_highest_educ_lvl',
							'parent2_highest_educ_lvl',
							# 'citizenship_country',
							'gini_indx',
							# 'pvrt_rate',
							'median_inc',
							# 'median_value',
							# 'educ_rate',
							'pct_blk',
							'pct_ai',
							# 'pct_asn',
							'pct_hawi',
							# 'pct_oth',
							'pct_two',
							# 'pct_non',
							'pct_hisp',
							'city_large',
							'city_mid',
							'city_small',
							'suburb_large',
							'suburb_mid',
							'suburb_small',
							# 'town_fringe',
							# 'town_distant',
							# 'town_remote',
							# 'rural_fringe',
							# 'rural_distant',
							# 'rural_remote',
							# 'AD_DTA',
							# 'AD_AST',
							# 'AP',
							# 'RS',
							# 'CHS',
							# 'IB',
							# 'AICE',
							# 'IB_AICE', 
							# 'term_credit_hours',
							# 'athlete',
							'remedial',
							# 'ACAD_PLAN',
							# 'plan_owner_org',
							# 'business',
							# 'cahnrs_anml',
							# 'cahnrs_envr',
							# 'cahnrs_econ',
							# 'cahnrext',
							# 'cas_chem',
							# 'cas_crim',
							# 'cas_math',
							# 'cas_psyc',
							# 'cas_biol',
							# 'cas_engl',
							# 'cas_phys',
							# 'cas',
							# 'comm',
							# 'education',
							# 'medicine',
							# 'nursing',
							# 'pharmacy',
							# 'provost',
							# 'vcea_bioe',
							# 'vcea_cive',
							# 'vcea_desn',
							# 'vcea_eecs',
							# 'vcea_mech',
							# 'vcea',
							# 'vet_med',
							# 'last_sch_proprietorship',
							# 'sat_erws',
							# 'sat_mss',
							# 'sat_comp',
							# 'attendee_alive',
							# 'attendee_campus_visit',
							# 'attendee_cashe',
							# 'attendee_destination',
							# 'attendee_experience',
							# 'attendee_fcd_pullman',
							# 'attendee_fced',
							# 'attendee_fcoc',
							# 'attendee_fcod',
							# 'attendee_group_visit',
							# 'attendee_honors_visit',
							# 'attendee_imagine_tomorrow',
							# 'attendee_imagine_u',
							# 'attendee_la_bienvenida',
							# 'attendee_lvp_camp',
							# 'attendee_oos_destination',
							# 'attendee_oos_experience',
							# 'attendee_preview',
							# 'attendee_preview_jrs',
							# 'attendee_shaping',
							# 'attendee_top_scholars',
							# 'attendee_transfer_day',
							# 'attendee_vibes',
							# 'attendee_welcome_center',
							# 'attendee_any_visitation_ind',
							# 'attendee_total_visits',
							# 'qvalue',
							# 'fed_efc',
							# 'fed_need',
							'unmet_need_ofr'
                            ]].dropna()

testing_set = testing_set.reset_index()

pred_outcome = testing_set[[ 
                            'emplid',
                            'ENRL_IND'
                            ]].copy(deep=True)

aggregate_outcome = testing_set[[ 
                            'emplid',
							'male',
							'underrep_minority',
							'first_gen_flag',
							'resident',
                            'ENRL_IND'
                            ]].copy(deep=True)

current_outcome = testing_set[[ 
                            'emplid',
                            'ENRL_IND'
                            ]].copy(deep=True)

#%%
# Detect and remove outliers
x_outlier = training_set.drop(columns='enrl_ind')

outlier_prep = make_column_transformer(
    (OneHotEncoder(drop='first'), [
									# 'race_hispanic',
									# 'race_american_indian',
									# 'race_alaska',
									# 'race_asian',
									# 'race_black',
									# 'race_native_hawaiian',
									# 'race_white',
                                    # 'acad_year', 
                                    # 'age_group',
                                    # 'marital_status',
                                    'first_gen_flag',
                                    # 'LSAMP_STEM_Flag',
                                    # 'anywhere_STEM_Flag',
                                    # 'afl_greek_indicator',
                                    # 'ACAD_PLAN',
                                    # 'plan_owner_org',
                                    # 'ipeds_ethnic_group_descrshort',
                                    # 'last_sch_proprietorship', 
                                    'parent1_highest_educ_lvl',
                                    'parent2_highest_educ_lvl'
                                    ]),
    remainder='passthrough'
)

x_outlier = outlier_prep.fit_transform(x_outlier)

training_set['mask'] = LocalOutlierFactor(metric='manhattan', n_jobs=-1).fit_predict(x_outlier)

outlier_set = training_set.drop(training_set[training_set['mask'] == 1].index)
outlier_set.to_csv('Z:\\Nathan\\Models\\student_risk\\outliers\\outlier_set.csv', encoding='utf-8', index=False)

training_set = training_set.drop(training_set[training_set['mask'] == -1].index)
training_set = training_set.drop(columns='mask')

#%%
# Create SMOTENC oversampled and Tomek Link undersampled training set
x_train = training_set.drop(columns=['enrl_ind','emplid'])

x_test = testing_set[[
                        # 'acad_year',
                        # 'age_group', 
                        # 'age',
                        'male',
                        # 'min_week_from_term_begin_dt',
                        # 'max_week_from_term_begin_dt',
                        'count_week_from_term_begin_dt',
                        # 'marital_status',
                        # 'Distance',
                        # 'pop_dens',
                        'underrep_minority', 
                        # 'ipeds_ethnic_group_descrshort',
                        'pell_eligibility_ind', 
                        # 'pell_recipient_ind',
                        'first_gen_flag', 
                        # 'LSAMP_STEM_Flag',
                        # 'anywhere_STEM_Flag',
                        # 'afl_greek_indicator',
                        'high_school_gpa',
                        # 'awe_instrument',
                        # 'cdi_instrument',
                        'avg_difficulty',
                        'avg_pct_withdrawn',
                        # 'avg_pct_CDFW',
                        'avg_pct_CDF',
                        # 'avg_pct_DFW',
                        # 'avg_pct_DF',
						'fall_lec_count',
						'fall_lab_count',
                        # 'fall_lec_contact_hrs',
                        # 'fall_lab_contact_hrs',
						# 'spring_lec_count',
						# 'spring_lab_count',
                        # 'spring_lec_contact_hrs',
                        # 'spring_lab_contact_hrs',
						'total_fall_contact_hrs',
                        'cum_adj_transfer_hours',
                        'resident',
                        # 'father_wsu_flag',
                        # 'mother_wsu_flag',
                        'parent1_highest_educ_lvl',
                        'parent2_highest_educ_lvl',
                        # 'citizenship_country',
                        'gini_indx',
                        # 'pvrt_rate',
                        'median_inc',
                        # 'median_value',
                        # 'educ_rate',
                        'pct_blk',
                        'pct_ai',
                        # 'pct_asn',
                        'pct_hawi',
                        # 'pct_oth',
                        'pct_two',
                        # 'pct_non',
                        'pct_hisp',
                        'city_large',
                        'city_mid',
                        'city_small',
                        'suburb_large',
                        'suburb_mid',
                        'suburb_small',
                        # 'town_fringe',
                        # 'town_distant',
                        # 'town_remote',
                        # 'rural_fringe',
                        # 'rural_distant',
                        # 'rural_remote',
                        # 'AD_DTA',
                        # 'AD_AST',
                        # 'AP',
                        # 'RS',
                        # 'CHS',
                        # 'IB',
                        # 'AICE',
                        # 'IB_AICE', 
                        # 'term_credit_hours',
                        # 'athlete',
                        'remedial',
                        # 'ACAD_PLAN',
                        # 'plan_owner_org',
                        # 'business',
                        # 'cahnrs_anml',
                        # 'cahnrs_envr',
                        # 'cahnrs_econ',
                        # 'cahnrext',
                        # 'cas_chem',
                        # 'cas_crim',
                        # 'cas_math',
                        # 'cas_psyc',
                        # 'cas_biol',
                        # 'cas_engl',
                        # 'cas_phys',
                        # 'cas',
                        # 'comm',
                        # 'education',
                        # 'medicine',
                        # 'nursing',
                        # 'pharmacy',
                        # 'provost',
                        # 'vcea_bioe',
                        # 'vcea_cive',
                        # 'vcea_desn',
                        # 'vcea_eecs',
                        # 'vcea_mech',
                        # 'vcea',
                        # 'vet_med',
                        # 'last_sch_proprietorship',
                        # 'sat_erws',
                        # 'sat_mss',
                        # 'sat_comp',
                        # 'attendee_alive',
                        # 'attendee_campus_visit',
                        # 'attendee_cashe',
                        # 'attendee_destination',
                        # 'attendee_experience',
                        # 'attendee_fcd_pullman',
                        # 'attendee_fced',
                        # 'attendee_fcoc',
                        # 'attendee_fcod',
                        # 'attendee_group_visit',
                        # 'attendee_honors_visit',
                        # 'attendee_imagine_tomorrow',
                        # 'attendee_imagine_u',
                        # 'attendee_la_bienvenida',
                        # 'attendee_lvp_camp',
                        # 'attendee_oos_destination',
                        # 'attendee_oos_experience',
                        # 'attendee_preview',
                        # 'attendee_preview_jrs',
                        # 'attendee_shaping',
                        # 'attendee_top_scholars',
                        # 'attendee_transfer_day',
                        # 'attendee_vibes',
                        # 'attendee_welcome_center',
                        # 'attendee_any_visitation_ind',
                        # 'attendee_total_visits',
                        # 'qvalue',
                        # 'fed_efc',
                        # 'fed_need',
                        'unmet_need_ofr'
                        ]]

y_train = training_set['enrl_ind']
y_test = testing_set['ENRL_IND']

smotenc_prep = make_column_transformer(
	(StandardScaler(), [
						# 'age',
						# 'min_week_from_term_begin_dt',
						# 'max_week_from_term_begin_dt',
						'count_week_from_term_begin_dt',
						# 'sat_erws',
						# 'sat_mss',
						# 'sat_comp',
						# 'attendee_total_visits',
						# 'Distance',
						# 'pop_dens', 
						# 'qvalue', 
						'median_inc',
						# 'median_value',
						# 'term_credit_hours',
						'high_school_gpa',
						# 'awe_instrument',
						# 'cdi_instrument',
						'avg_difficulty',
						'avg_pct_withdrawn',
                        'avg_pct_CDF',
						'fall_lec_count',
						'fall_lab_count',
						# 'fall_lec_contact_hrs',
						# 'fall_lab_contact_hrs',
						# 'spring_lec_count',
						# 'spring_lab_count',
						# 'spring_lec_contact_hrs',
						# 'spring_lab_contact_hrs',
						'total_fall_contact_hrs',
						# 'total_spring_contact_hrs',
						'cum_adj_transfer_hours',
						# 'term_credit_hours',
						# 'fed_efc',
						# 'fed_need', 
						'unmet_need_ofr'
						]),
	(OneHotEncoder(drop='first'), [
									# 'race_hispanic',
									# 'race_american_indian',
									# 'race_alaska',
									# 'race_asian',
									# 'race_black',
									# 'race_native_hawaiian',
									# 'race_white',
                                    # 'acad_year', 
                                    # 'age_group',
                                    # 'marital_status',
                                    'first_gen_flag',
                                    # 'LSAMP_STEM_Flag',
                                    # 'anywhere_STEM_Flag',
                                    # 'afl_greek_indicator',
                                    # 'ACAD_PLAN',
                                    # 'plan_owner_org',
                                    # 'ipeds_ethnic_group_descrshort',
                                    # 'last_sch_proprietorship', 
                                    'parent1_highest_educ_lvl',
                                    'parent2_highest_educ_lvl'
                                    ]),
    remainder='passthrough'
)

x_train = smotenc_prep.fit_transform(x_train)
x_test = smotenc_prep.fit_transform(x_test)

# over = SMOTENC(categorical_features=[11,12,13,14,15,16,17,18,19,20,21,28,29,30,31,32,33,34], sampling_strategy='minority', k_neighbors=2, n_jobs=-1)
# x_train, y_train = over.fit_resample(x_train, y_train)

under = TomekLinks(sampling_strategy='all', n_jobs=-1)
x_train, y_train = under.fit_resample(x_train, y_train)

tomek_index = under.sample_indices_
training_set = training_set.reset_index(drop=True)

tomek_set = training_set.drop(tomek_index)
tomek_set.to_csv('Z:\\Nathan\\Models\\student_risk\\outliers\\tomek_set.csv', encoding='utf-8', index=False)

#%%
# Standard logistic model
y, x = dmatrices('enrl_ind ~ male + underrep_minority + pct_blk + pct_ai + pct_hawi + pct_two + pct_hisp \
                + city_large + city_mid + city_small + suburb_large + suburb_mid + suburb_small \
                + pell_eligibility_ind \
                + first_gen_flag \
                + avg_difficulty + avg_pct_CDF + avg_pct_withdrawn \
				+ fall_lec_count + fall_lab_count \
				+ total_fall_contact_hrs \
                + resident + gini_indx + median_inc \
            	+ high_school_gpa + remedial \
            	+ unmet_need_ofr', data=logit_df, return_type='dataframe')

logit_mod = Logit(y, x)
logit_res = logit_mod.fit(maxiter=500)
print(logit_res.summary())

print('\n')

#%%
# VIF diagnostic
vif = pd.DataFrame()
vif['vif factor'] = [variance_inflation_factor(x.values, i) for i in range(x.shape[1])]
vif['features'] = x.columns
print(vif.round(1))

print('\n')

#%%
print('Run machine learning models...\n')

# Logistic model
lreg = LogisticRegression(penalty='elasticnet', solver='saga', class_weight='balanced', max_iter=1000, l1_ratio=0.0, C=1.0, n_jobs=-1, verbose=True).fit(x_train, y_train)

lreg_probs = lreg.predict_proba(x_train)
lreg_probs = lreg_probs[:, 1]
lreg_auc = roc_auc_score(y_train, lreg_probs)

print(f'\nOverall accuracy for logistic model (training): {lreg.score(x_train, y_train):.4f}')
print(f'ROC AUC for logistic model (training): {lreg_auc:.4f}\n')

lreg_fpr, lreg_tpr, thresholds = roc_curve(y_train, lreg_probs, drop_intermediate=False)

#%%
# SGD model
sgd = SGDClassifier(loss='modified_huber', penalty='elasticnet', class_weight='balanced', early_stopping=False, max_iter=2000, l1_ratio=0.0, learning_rate='adaptive', eta0=0.0001, tol=0.0001, n_iter_no_change=100, n_jobs=-1, verbose=True).fit(x_train, y_train)

sgd_probs = sgd.predict_proba(x_train)
sgd_probs = sgd_probs[:, 1]
sgd_auc = roc_auc_score(y_train, sgd_probs)

print(f'\nOverall accuracy for SGD model (training): {sgd.score(x_train, y_train):.4f}')
print(f'ROC AUC for SGD model (training): {sgd_auc:.4f}\n')

sgd_fpr, sgd_tpr, thresholds = roc_curve(y_train, sgd_probs, drop_intermediate=False)

#%%
# SVC model
# svc = SVC(kernel='linear', class_weight='balanced', probability=True, verbose=True, shrinking=False).fit(x_train, y_train)

# svc_probs = svc.predict_proba(x_train)
# svc_probs = svc_probs[:, 1]
# svc_auc = roc_auc_score(y_train, svc_probs)

# print(f'\n\nOverall accuracy for linear SVC model (training): {svc.score(x_train, y_train):.4f}')
# print(f'ROC AUC for linear SVC model (training): {svc_auc:.4f}\n')

# svc_fpr, svc_tpr, thresholds = roc_curve(y_train, svc_probs, drop_intermediate=False)

#%%
# Random forest model
rfc = RandomForestClassifier(n_estimators=500, class_weight='balanced', max_depth=10, max_features='sqrt', n_jobs=-1, verbose=True).fit(x_train, y_train)

rfc_probs = rfc.predict_proba(x_train)
rfc_probs = rfc_probs[:, 1]
rfc_auc = roc_auc_score(y_train, rfc_probs)

print(f'\nOverall accuracy for random forest model (training): {rfc.score(x_train, y_train):.4f}')
print(f'ROC AUC for random forest model (training): {rfc_auc:.4f}\n')

rfc_fpr, rfc_tpr, thresholds = roc_curve(y_train, rfc_probs, drop_intermediate=False)

#%%
# Multi-layer perceptron model
# mlp = MLPClassifier(hidden_layer_sizes=(75,50,25), activation='relu', solver='sgd', alpha=2.5, learning_rate_init=0.001, n_iter_no_change=10, max_iter=2000, verbose=True).fit(x_train, y_train)

# mlp_probs = mlp.predict_proba(x_train)
# mlp_probs = mlp_probs[:, 1]
# mlp_auc = roc_auc_score(y_train, mlp_probs)

# print(f'\nOverall accuracy for multi-layer perceptron model (training): {mlp.score(x_train, y_train):.4f}')
# print(f'ROC AUC for multi-layer perceptron model (training): {mlp_auc:.4f}\n')

# mlp_fpr, mlp_tpr, thresholds = roc_curve(y_train, mlp_probs, drop_intermediate=False)

#%%
# Ensemble model
vcf = VotingClassifier(estimators=[('lreg', lreg), ('sgd', sgd), ('rfc', rfc)], voting='soft', weights=[1, 1, 1]).fit(x_train, y_train)

vcf_probs = vcf.predict_proba(x_train)
vcf_probs = vcf_probs[:, 1]
vcf_auc = roc_auc_score(y_train, vcf_probs)

print(f'\nOverall accuracy for ensemble model (training): {vcf.score(x_train, y_train):.4f}')
print(f'ROC AUC for ensemble model (training): {vcf_auc:.4f}\n')

vcf_fpr, vcf_tpr, thresholds = roc_curve(y_train, vcf_probs, drop_intermediate=False)

#%%
# Prepare model predictions
print('Prepare model predictions...')

lreg_pred_probs = lreg.predict_proba(x_test)
lreg_pred_probs = lreg_pred_probs[:, 1]
sgd_pred_probs = sgd.predict_proba(x_test)
sgd_pred_probs = sgd_pred_probs[:, 1]
# svc_pred_probs = svc.predict_proba(x_test)
# svc_pred_probs = svc_pred_probs[:, 1]
rfc_pred_probs = rfc.predict_proba(x_test)
rfc_pred_probs = rfc_pred_probs[:, 1]
# mlp_pred_probs = mlp.predict_proba(x_test)
# mlp_pred_probs = mlp_pred_probs[:, 1]
vcf_pred_probs = vcf.predict_proba(x_test)
vcf_pred_probs = vcf_pred_probs[:, 1]

print('Done\n')

#%%
# Output model predictions to file
print('Output model predictions and model...')

pred_outcome['lr_prob'] = pd.DataFrame(lreg_pred_probs)
pred_outcome['lr_pred'] = lreg.predict(x_test)
pred_outcome['sgd_prob'] = pd.DataFrame(sgd_pred_probs)
pred_outcome['sgd_pred'] = sgd.predict(x_test)
# pred_outcome['svc_prob'] = pd.DataFrame(svc_pred_probs)
# pred_outcome['svc_pred'] = svc.predict(x_test)
pred_outcome['rfc_prob'] = pd.DataFrame(rfc_pred_probs)
pred_outcome['rfc_pred'] = rfc.predict(x_test)
# pred_outcome['mlp_prob'] = pd.DataFrame(mlp_pred_probs)
# pred_outcome['mlp_pred'] = mlp.predict(x_test)
pred_outcome['vcf_prob'] = pd.DataFrame(vcf_pred_probs)
pred_outcome['vcf_pred'] = vcf.predict(x_test)
pred_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\pred_outcome.csv', encoding='utf-8', index=False)

#%%
aggregate_outcome['emplid'] = aggregate_outcome['emplid'].astype(str).str.zfill(9)
aggregate_outcome['risk_prob'] = 1 - pd.DataFrame(vcf_pred_probs).round(4)

aggregate_outcome = aggregate_outcome.rename(columns={"male": "sex_ind"})
aggregate_outcome.loc[aggregate_outcome['sex_ind'] == 1, 'sex_descr'] = 'Male'
aggregate_outcome.loc[aggregate_outcome['sex_ind'] == 0, 'sex_descr'] = 'Female'

aggregate_outcome = aggregate_outcome.rename(columns={"underrep_minority": "underrep_minority_ind"})
aggregate_outcome.loc[aggregate_outcome['underrep_minority_ind'] == 1, 'underrep_minority_descr'] = 'Minority'
aggregate_outcome.loc[aggregate_outcome['underrep_minority_ind'] == 0, 'underrep_minority_descr'] = 'Non-minority'

aggregate_outcome = aggregate_outcome.rename(columns={"resident": "resident_ind"})
aggregate_outcome.loc[aggregate_outcome['resident_ind'] == 1, 'resident_descr'] = 'Resident'
aggregate_outcome.loc[aggregate_outcome['resident_ind'] == 0, 'resident_descr'] = 'non-Resident'

aggregate_outcome.loc[aggregate_outcome['first_gen_flag'] == 'Y', 'first_gen_flag'] = 1
aggregate_outcome.loc[aggregate_outcome['first_gen_flag'] == 'N', 'first_gen_flag'] = 0

aggregate_outcome = aggregate_outcome.rename(columns={"first_gen_flag": "first_gen_ind"})
aggregate_outcome.loc[aggregate_outcome['first_gen_ind'] == 1, 'first_gen_descr'] = 'non-First Gen'
aggregate_outcome.loc[aggregate_outcome['first_gen_ind'] == 0, 'first_gen_descr'] = 'First Gen'

#%%
aggregate_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\aggregate_outcome.csv', encoding='utf-8', index=False)
# aggregate_outcome.to_sql('aggregate_outcome', con=auto_engine, if_exists='replace', index=False, schema='oracle_int.dbo')

#%%
current_outcome['emplid'] = current_outcome['emplid'].astype(str).str.zfill(9)
current_outcome['risk_prob'] = 1 - pd.DataFrame(vcf_pred_probs).round(4)

# current_outcome.loc[current_outcome['risk_prob'] >= .6666,'risk_level_idx'] = '3'
# current_outcome.loc[(current_outcome['risk_prob'] < .6666) & (current_outcome['risk_prob'] >= .3333) ,'risk_level_idx'] = '2'
# current_outcome.loc[current_outcome['risk_prob'] < .3333,'risk_level_idx'] = '1'

# current_outcome.loc[current_outcome['risk_prob'] >= .6666,'risk_level_descr'] = 'High'
# current_outcome.loc[(current_outcome['risk_prob'] < .6666) & (current_outcome['risk_prob'] >= .3333) ,'risk_level_descr'] = 'Mid'
# current_outcome.loc[current_outcome['risk_prob'] < .3333,'risk_level_descr'] = 'Low'

current_outcome['date'] = date.today()
current_outcome['model_id'] = 1

#%%
if not os.path.isfile('Z:\\Nathan\\Models\\student_risk\\predictions\\student_outcome.csv'):
	current_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\student_outcome.csv', encoding='utf-8', index=False)
	current_outcome.to_sql('student_outcome', con=auto_engine, if_exists='append', index=False, schema='oracle_int.dbo')
else:
	prior_outcome = pd.read_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\student_outcome.csv', encoding='utf-8', low_memory=False)
	prior_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\student_backup.csv', encoding='utf-8', index=False)
	student_outcome = pd.concat([prior_outcome, current_outcome])
	student_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\student_outcome.csv', encoding='utf-8', index=False)
	current_outcome.to_sql('student_outcome', con=auto_engine, if_exists='append', index=False, schema='oracle_int.dbo')

#%%
# Output model
joblib.dump(vcf, f'Z:\\Nathan\\Models\\student_risk\\models\\model_v{sklearn.__version__}.pkl')

print('Done\n')