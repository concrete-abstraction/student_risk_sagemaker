#%%
from student_risk import build_prod, config
import csv
import datetime
import joblib
import numpy as np
import pandas as pd
import pathlib
import pyodbc
import os
import saspy
import shap
import sklearn
import sqlalchemy
import urllib
from datetime import date
from patsy import dmatrices
from imblearn.under_sampling import TomekLinks, NearMiss
from itertools import islice
from sklearn.compose import make_column_transformer
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.ensemble import VotingClassifier
from sklearn.metrics import roc_curve, roc_auc_score
from statsmodels.discrete.discrete_model import Logit
from statsmodels.stats.outliers_influence import variance_inflation_factor
from sqlalchemy import MetaData, Table
from xgboost import XGBClassifier

#%%
# Database connection
cred = pathlib.Path('Z:\\Nathan\\Models\\student_risk\\login.bin').read_text().split('|')
params = urllib.parse.quote_plus(f'TRUSTED_CONNECTION=YES; DRIVER={{SQL Server Native Client 11.0}}; SERVER={cred[0]}; DATABASE={cred[1]}')
engine = sqlalchemy.create_engine(f'mssql+pyodbc:///?odbc_connect={params}')
auto_engine = engine.execution_options(autocommit=True, isolation_level='AUTOCOMMIT')
metadata_engine = MetaData(engine.execution_options(autocommit=True, isolation_level='AUTOCOMMIT'))
student_shap = Table('student_shap', metadata_engine, autoload=True)

#%%
# Global variable intialization
strm = None
top_N = 5
model_id = 3
day_of_week = 5
run_date = date.today()

#%%
# Midterm date and snapshot check
calendar = pd.read_csv('Z:\\Nathan\\Models\\student_risk\\supplemental_files\\acad_calendar.csv', encoding='utf-8', parse_dates=True).fillna(9999)
now = datetime.datetime.now()

now_day = now.day
now_month = now.month
now_year = now.year

strm = calendar[(calendar['term_year'] == now_year) & (calendar['begin_month'] <= now_month) & (calendar['end_month'] >= now_month)]['STRM'].values[0]

midterm_day = calendar[(calendar['term_year'] == now_year) & (calendar['begin_month'] <= now_month) & (calendar['end_month'] >= now_month)]['midterm_day'].values[0]
midterm_month = calendar[(calendar['term_year'] == now_year) & (calendar['begin_month'] <= now_month) & (calendar['end_month'] >= now_month)]['midterm_month'].values[0]
midterm_year = calendar[(calendar['term_year'] == now_year) & (calendar['begin_month'] <= now_month) & (calendar['end_month'] >= now_month)]['midterm_year'].values[0]

if now_year < midterm_year:
	raise config.MidError(f'{date.today()}: Midterm year exception, attempting to run if midterm newest snapshot.')

elif (now_year == midterm_year and now_month < midterm_month):
	raise config.MidError(f'{date.today()}: Midterm month exception, attempting to run if midterm newest snapshot.')

elif (now_year == midterm_year and now_month == midterm_month and now_day < midterm_day):
	raise config.MidError(f'{date.today()}: Midterm day exception, attempting to run if midterm newest snapshot.')

else:
	sas = saspy.SASsession()

	sas.symput('strm', strm)

	sas.submit("""
	%let dsn = census;

	libname &dsn. odbc dsn=&dsn. schema=dbo;

	proc sql;
		select distinct
			max(case when snapshot = 'census' 	then 1
				when snapshot = 'midterm' 		then 2
				when snapshot = 'eot'			then 3
												else 0
												end) as snap_order
			into: snap_check
			separated by ''
		from &dsn..class_registration
		where acad_career = 'UGRD'
			and strm = (select distinct
							max(strm)
						from &dsn..class_registration where acad_career = 'UGRD')
	;quit;
	""")

	snap_check = sas.symget('snap_check')

	sas.endsas()

	if snap_check != 2:
		raise config.MidError(f'{date.today()}: No midterm date exception but snapshot exception, attempting to run from census.')

	else:
		print(f'{date.today()}: No midterm date or snapshot exceptions, running from midterm.')

#%%
# SAS dataset builder
build_prod.DatasetBuilderProd.build_census_prod()

#%%
# Import pre-split data
training_set = pd.read_csv('Z:\\Nathan\\Models\\student_risk\\datasets\\training_set.csv', encoding='utf-8', low_memory=False)
testing_set = pd.read_csv('Z:\\Nathan\\Models\\student_risk\\datasets\\testing_set.csv', encoding='utf-8', low_memory=False)

#%%
# Prepare dataframes
print('\nPrepare dataframes and preprocess data...')

# Pullman dataframes
pullm_logit_df = training_set[(training_set['adj_acad_prog_primary_campus'] == 'PULLM') & (training_set['adj_admit_type_cat'] == 'FRSH')][[
                        'enrl_ind', 
                        # 'acad_year',
						# 'age_group', 
						# 'age',
						'male',
						# 'race_hispanic',
						# 'race_american_indian',
						# 'race_alaska',
						# 'race_asian',
						# 'race_black',
						# 'race_native_hawaiian',
						# 'race_white',
						# 'min_week_from_term_begin_dt',
						# 'max_week_from_term_begin_dt',
						'count_week_from_term_begin_dt',
						# 'marital_status',
						'acs_mi',
						'distance',
						'pop_dens',
						'underrep_minority', 
						# 'ipeds_ethnic_group_descrshort',
						'pell_eligibility_ind',
						# 'pell_recipient_ind',
						'first_gen_flag',
						'first_gen_flag_mi', 
						# 'LSAMP_STEM_Flag',
						# 'anywhere_STEM_Flag',
						'honors_program_ind',
						# 'afl_greek_indicator',
						'high_school_gpa',
						'high_school_gpa_mi',
						'fall_midterm_gpa_avg',
						'fall_midterm_gpa_avg_mi',
						'fall_midterm_grade_count',
						'fall_midterm_S_grade_count',
						'fall_midterm_W_grade_count',
						# 'awe_instrument',
						# 'cdi_instrument',
						'fall_avg_difficulty',
						'fall_avg_pct_withdrawn',
						# 'fall_avg_pct_CDFW',
						'fall_avg_pct_CDF',
						# 'fall_avg_pct_DFW',
						# 'fall_avg_pct_DF',
						# 'fall_crse_mi',
						'fall_lec_count',
						'fall_lab_count',
						# 'fall_int_count',
						'fall_stu_count',
						# 'fall_sem_count',
						'fall_oth_count',
						# 'fall_lec_contact_hrs',
						# 'fall_lab_contact_hrs',
						# 'fall_int_contact_hrs',
						# 'fall_stu_contact_hrs',
						# 'fall_sem_contact_hrs',
						# 'fall_oth_contact_hrs',
						# 'total_fall_contact_hrs',
						'cum_adj_transfer_hours',
						'resident',
						# 'father_wsu_flag',
						# 'mother_wsu_flag',
						'parent1_highest_educ_lvl',
						'parent2_highest_educ_lvl',
						# 'citizenship_country',
						'gini_indx',
						'pvrt_rate',
						'median_inc',
						'median_value',
						'educ_rate',
						'pct_blk',
						'pct_ai',
						'pct_asn',
						'pct_hawi',
						'pct_oth',
						'pct_two',
						# 'pct_non',
						'pct_hisp',
						# 'city_large',
						# 'city_mid',
						# 'city_small',
						# 'suburb_large',
						# 'suburb_mid',
						# 'suburb_small',
						# 'town_fringe',
						# 'town_distant',
						# 'town_remote',
						# 'rural_fringe',
						# 'rural_distant',
						# 'rural_remote',
						'AD_DTA',
						'AD_AST',
						'AP',
						'RS',
						'CHS',
						# 'IB',
						# 'AICE',
						'IB_AICE', 
						'fall_credit_hours',
						# 'total_fall_units',
						'fall_withdrawn_hours',
						# 'fall_withdrawn_ind',
						# 'athlete',
						'remedial',
						# 'ACAD_PLAN',
						# 'plan_owner_org',
						'business',
						'cahnrs_anml',
						# 'cahnrs_envr',
						'cahnrs_econ',
						'cahnrext',
						'cas_chem',
						'cas_crim',
						'cas_math',
						'cas_psyc',
						'cas_biol',
						'cas_engl',
						'cas_phys',
						'cas',
						'comm',
						'education',
						'medicine',
						'nursing',
						# 'pharmacy',
						# 'provost',
						'vcea_bioe',
						'vcea_cive',
						'vcea_desn',
						'vcea_eecs',
						'vcea_mech',
						'vcea',
						'vet_med',
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
						'unmet_need_ofr',
						'unmet_need_ofr_mi'
                        ]].dropna()

pullm_training_set = training_set[(training_set['adj_acad_prog_primary_campus'] == 'PULLM') & (training_set['adj_admit_type_cat'] == 'FRSH')][[
                            'emplid',
                            'enrl_ind', 
	                        # 'acad_year',
							# 'age_group', 
							# 'age',
							'male',
							# 'race_hispanic',
							# 'race_american_indian',
							# 'race_alaska',
							# 'race_asian',
							# 'race_black',
							# 'race_native_hawaiian',
							# 'race_white',
							# 'min_week_from_term_begin_dt',
							# 'max_week_from_term_begin_dt',
							'count_week_from_term_begin_dt',
							# 'marital_status',
							'acs_mi',
							'distance',
							'pop_dens',
							'underrep_minority', 
							# 'ipeds_ethnic_group_descrshort',
							'pell_eligibility_ind',
							# 'pell_recipient_ind',
							'first_gen_flag',
							'first_gen_flag_mi', 
							# 'LSAMP_STEM_Flag',
							# 'anywhere_STEM_Flag',
							'honors_program_ind',
							# 'afl_greek_indicator',
							'high_school_gpa',
							'high_school_gpa_mi',
							'fall_midterm_gpa_avg',
							'fall_midterm_gpa_avg_mi',
							'fall_midterm_grade_count',
							'fall_midterm_S_grade_count',
							'fall_midterm_W_grade_count',
							# 'awe_instrument',
							# 'cdi_instrument',
							'fall_avg_difficulty',
							'fall_avg_pct_withdrawn',
							# 'fall_avg_pct_CDFW',
							'fall_avg_pct_CDF',
							# 'fall_avg_pct_DFW',
							# 'fall_avg_pct_DF',
							# 'fall_crse_mi',
							'fall_lec_count',
							'fall_lab_count',
							# 'fall_int_count',
							'fall_stu_count',
							# 'fall_sem_count',
							'fall_oth_count',
							# 'fall_lec_contact_hrs',
							# 'fall_lab_contact_hrs',
							# 'fall_int_contact_hrs',
							# 'fall_stu_contact_hrs',
							# 'fall_sem_contact_hrs',
							# 'fall_oth_contact_hrs',
							# 'total_fall_contact_hrs',
							'cum_adj_transfer_hours',
							'resident',
							# 'father_wsu_flag',
							# 'mother_wsu_flag',
							'parent1_highest_educ_lvl',
							'parent2_highest_educ_lvl',
							# 'citizenship_country',
							'gini_indx',
							'pvrt_rate',
							'median_inc',
							'median_value',
							'educ_rate',
							'pct_blk',
							'pct_ai',
							'pct_asn',
							'pct_hawi',
							'pct_oth',
							'pct_two',
							# 'pct_non',
							'pct_hisp',
							# 'city_large',
							# 'city_mid',
							# 'city_small',
							# 'suburb_large',
							# 'suburb_mid',
							# 'suburb_small',
							# 'town_fringe',
							# 'town_distant',
							# 'town_remote',
							# 'rural_fringe',
							# 'rural_distant',
							# 'rural_remote',
							'AD_DTA',
							'AD_AST',
							'AP',
							'RS',
							'CHS',
							# 'IB',
							# 'AICE',
							'IB_AICE', 
							'fall_credit_hours',
							# 'total_fall_units',
							'fall_withdrawn_hours',
							# 'fall_withdrawn_ind',
							# 'athlete',
							'remedial',
							# 'ACAD_PLAN',
							# 'plan_owner_org',
							'business',
							'cahnrs_anml',
							# 'cahnrs_envr',
							'cahnrs_econ',
							'cahnrext',
							'cas_chem',
							'cas_crim',
							'cas_math',
							'cas_psyc',
							'cas_biol',
							'cas_engl',
							'cas_phys',
							'cas',
							'comm',
							'education',
							'medicine',
							'nursing',
							# 'pharmacy',
							# 'provost',
							'vcea_bioe',
							'vcea_cive',
							'vcea_desn',
							'vcea_eecs',
							'vcea_mech',
							'vcea',
							'vet_med',
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
							'unmet_need_ofr',
							'unmet_need_ofr_mi'
                            ]].dropna()

pullm_testing_set = testing_set[(testing_set['adj_acad_prog_primary_campus'] == 'PULLM') & (testing_set['adj_admit_type_cat'] == 'FRSH')][[
                            'emplid',
                            # 'enrl_ind', 
	                        # 'acad_year',
							# 'age_group', 
							# 'age',
							'male',
							# 'race_hispanic',
							# 'race_american_indian',
							# 'race_alaska',
							# 'race_asian',
							# 'race_black',
							# 'race_native_hawaiian',
							# 'race_white',
							# 'min_week_from_term_begin_dt',
							# 'max_week_from_term_begin_dt',
							'count_week_from_term_begin_dt',
							# 'marital_status',
							'acs_mi',
							'distance',
							'pop_dens',
							'underrep_minority', 
							# 'ipeds_ethnic_group_descrshort',
							'pell_eligibility_ind',
							# 'pell_recipient_ind',
							'first_gen_flag',
							'first_gen_flag_mi', 
							# 'LSAMP_STEM_Flag',
							# 'anywhere_STEM_Flag',
							'honors_program_ind',
							# 'afl_greek_indicator',
							'high_school_gpa',
							'high_school_gpa_mi',
							'fall_midterm_gpa_avg',
							'fall_midterm_gpa_avg_mi',
							'fall_midterm_grade_count',
							'fall_midterm_S_grade_count',
							'fall_midterm_W_grade_count',
							# 'awe_instrument',
							# 'cdi_instrument',
							'fall_avg_difficulty',
							'fall_avg_pct_withdrawn',
							# 'fall_avg_pct_CDFW',
							'fall_avg_pct_CDF',
							# 'fall_avg_pct_DFW',
							# 'fall_avg_pct_DF',
							# 'fall_crse_mi',
							'fall_lec_count',
							'fall_lab_count',
							# 'fall_int_count',
							'fall_stu_count',
							# 'fall_sem_count',
							'fall_oth_count',
							# 'fall_lec_contact_hrs',
							# 'fall_lab_contact_hrs',
							# 'fall_int_contact_hrs',
							# 'fall_stu_contact_hrs',
							# 'fall_sem_contact_hrs',
							# 'fall_oth_contact_hrs',
							# 'total_fall_contact_hrs',
							'cum_adj_transfer_hours',
							'resident',
							# 'father_wsu_flag',
							# 'mother_wsu_flag',
							'parent1_highest_educ_lvl',
							'parent2_highest_educ_lvl',
							# 'citizenship_country',
							'gini_indx',
							'pvrt_rate',
							'median_inc',
							'median_value',
							'educ_rate',
							'pct_blk',
							'pct_ai',
							'pct_asn',
							'pct_hawi',
							'pct_oth',
							'pct_two',
							# 'pct_non',
							'pct_hisp',
							# 'city_large',
							# 'city_mid',
							# 'city_small',
							# 'suburb_large',
							# 'suburb_mid',
							# 'suburb_small',
							# 'town_fringe',
							# 'town_distant',
							# 'town_remote',
							# 'rural_fringe',
							# 'rural_distant',
							# 'rural_remote',
							'AD_DTA',
							'AD_AST',
							'AP',
							'RS',
							'CHS',
							# 'IB',
							# 'AICE',
							'IB_AICE', 
							'fall_credit_hours',
							# 'total_fall_units',
							'fall_withdrawn_hours',
							# 'fall_withdrawn_ind',
							# 'athlete',
							'remedial',
							# 'ACAD_PLAN',
							# 'plan_owner_org',
							'business',
							'cahnrs_anml',
							# 'cahnrs_envr',
							'cahnrs_econ',
							'cahnrext',
							'cas_chem',
							'cas_crim',
							'cas_math',
							'cas_psyc',
							'cas_biol',
							'cas_engl',
							'cas_phys',
							'cas',
							'comm',
							'education',
							'medicine',
							'nursing',
							# 'pharmacy',
							# 'provost',
							'vcea_bioe',
							'vcea_cive',
							'vcea_desn',
							'vcea_eecs',
							'vcea_mech',
							'vcea',
							'vet_med',
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
							'unmet_need_ofr',
							'unmet_need_ofr_mi'
                            ]].dropna()

pullm_testing_set = pullm_testing_set.reset_index()

pullm_shap_outcome = pullm_testing_set['emplid'].copy(deep=True).values.tolist()

pullm_pred_outcome = pullm_testing_set[[ 
                            'emplid',
                            # 'enrl_ind'
                            ]].copy(deep=True)

pullm_aggregate_outcome = pullm_testing_set[[ 
                            'emplid',
							'male',
							'underrep_minority',
							'first_gen_flag',
							'resident'
                            # 'enrl_ind'
                            ]].copy(deep=True)

pullm_current_outcome = pullm_testing_set[[ 
                            'emplid',
                            # 'enrl_ind'
                            ]].copy(deep=True)

#%%
# Vancouver dataframes
vanco_logit_df = training_set[(training_set['adj_acad_prog_primary_campus'] == 'VANCO') & (training_set['adj_admit_type_cat'] == 'FRSH')][[
                        'enrl_ind', 
                        # 'acad_year',
						# 'age_group', 
						# 'age',
						'male',
						# 'race_hispanic',
						# 'race_american_indian',
						# 'race_alaska',
						# 'race_asian',
						# 'race_black',
						# 'race_native_hawaiian',
						# 'race_white',
						# 'min_week_from_term_begin_dt',
						# 'max_week_from_term_begin_dt',
						'count_week_from_term_begin_dt',
						# 'marital_status',
						'acs_mi',
						'distance',
						'pop_dens',
						'underrep_minority', 
						# 'ipeds_ethnic_group_descrshort',
						'pell_eligibility_ind',
						# 'pell_recipient_ind',
						'first_gen_flag',
						'first_gen_flag_mi', 
						# 'LSAMP_STEM_Flag',
						# 'anywhere_STEM_Flag',
						# 'honors_program_ind',
						# 'afl_greek_indicator',
						'high_school_gpa',
						'high_school_gpa_mi',
						'fall_midterm_gpa_avg',
						'fall_midterm_gpa_avg_mi',
						'fall_midterm_grade_count',
						# 'fall_midterm_S_grade_count',
						# 'fall_midterm_W_grade_count',
						# 'awe_instrument',
						# 'cdi_instrument',
						'fall_avg_difficulty',
						'fall_avg_pct_withdrawn',
						# 'fall_avg_pct_CDFW',
						'fall_avg_pct_CDF',
						# 'fall_avg_pct_DFW',
						# 'fall_avg_pct_DF',
						# 'fall_crse_mi',
						'fall_lec_count',
						'fall_lab_count',
						# 'fall_int_count',
						# 'fall_stu_count',
						# 'fall_sem_count',
						# 'fall_oth_count',
						# 'fall_lec_contact_hrs',
						# 'fall_lab_contact_hrs',
						# 'fall_int_contact_hrs',
						# 'fall_stu_contact_hrs',
						# 'fall_sem_contact_hrs',
						# 'fall_oth_contact_hrs',
						# 'total_fall_contact_hrs',
						'cum_adj_transfer_hours',
						'resident',
						# 'father_wsu_flag',
						# 'mother_wsu_flag',
						'parent1_highest_educ_lvl',
						'parent2_highest_educ_lvl',
						# 'citizenship_country',
						'gini_indx',
						'pvrt_rate',
						'median_inc',
						'median_value',
						'educ_rate',
						'pct_blk',
						'pct_ai',
						'pct_asn',
						'pct_hawi',
						'pct_oth',
						'pct_two',
						# 'pct_non',
						'pct_hisp',
						# 'city_large',
						# 'city_mid',
						# 'city_small',
						# 'suburb_large',
						# 'suburb_mid',
						# 'suburb_small',
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
						'fall_credit_hours',
						# 'total_fall_units',
						'fall_withdrawn_hours',
						# 'fall_withdrawn_ind',
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
						'unmet_need_ofr',
						'unmet_need_ofr_mi'
                        ]].dropna()

vanco_training_set = training_set[(training_set['adj_acad_prog_primary_campus'] == 'VANCO') & (training_set['adj_admit_type_cat'] == 'FRSH')][[
                            'emplid',
                            'enrl_ind', 
							# 'acad_year',
							# 'age_group', 
							# 'age',
							'male',
							# 'race_hispanic',
							# 'race_american_indian',
							# 'race_alaska',
							# 'race_asian',
							# 'race_black',
							# 'race_native_hawaiian',
							# 'race_white',
							# 'min_week_from_term_begin_dt',
							# 'max_week_from_term_begin_dt',
							'count_week_from_term_begin_dt',
							# 'marital_status',
							'acs_mi',
							'distance',
							'pop_dens',
							'underrep_minority', 
							# 'ipeds_ethnic_group_descrshort',
							'pell_eligibility_ind',
							# 'pell_recipient_ind',
							'first_gen_flag',
							'first_gen_flag_mi', 
							# 'LSAMP_STEM_Flag',
							# 'anywhere_STEM_Flag',
							# 'honors_program_ind',
							# 'afl_greek_indicator',
							'high_school_gpa',
							'high_school_gpa_mi',
							'fall_midterm_gpa_avg',
							'fall_midterm_gpa_avg_mi',
							'fall_midterm_grade_count',
							# 'fall_midterm_S_grade_count',
							# 'fall_midterm_W_grade_count',
							# 'awe_instrument',
							# 'cdi_instrument',
							'fall_avg_difficulty',
							'fall_avg_pct_withdrawn',
							# 'fall_avg_pct_CDFW',
							'fall_avg_pct_CDF',
							# 'fall_avg_pct_DFW',
							# 'fall_avg_pct_DF',
							# 'fall_crse_mi',
							'fall_lec_count',
							'fall_lab_count',
							# 'fall_int_count',
							# 'fall_stu_count',
							# 'fall_sem_count',
							# 'fall_oth_count',
							# 'fall_lec_contact_hrs',
							# 'fall_lab_contact_hrs',
							# 'fall_int_contact_hrs',
							# 'fall_stu_contact_hrs',
							# 'fall_sem_contact_hrs',
							# 'fall_oth_contact_hrs',
							# 'total_fall_contact_hrs',
							'cum_adj_transfer_hours',
							'resident',
							# 'father_wsu_flag',
							# 'mother_wsu_flag',
							'parent1_highest_educ_lvl',
							'parent2_highest_educ_lvl',
							# 'citizenship_country',
							'gini_indx',
							'pvrt_rate',
							'median_inc',
							'median_value',
							'educ_rate',
							'pct_blk',
							'pct_ai',
							'pct_asn',
							'pct_hawi',
							'pct_oth',
							'pct_two',
							# 'pct_non',
							'pct_hisp',
							# 'city_large',
							# 'city_mid',
							# 'city_small',
							# 'suburb_large',
							# 'suburb_mid',
							# 'suburb_small',
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
							'fall_credit_hours',
							# 'total_fall_units',
							'fall_withdrawn_hours',
							# 'fall_withdrawn_ind',
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
							'unmet_need_ofr',
							'unmet_need_ofr_mi'
                            ]].dropna()

vanco_testing_set = testing_set[(testing_set['adj_acad_prog_primary_campus'] == 'VANCO') & (testing_set['adj_admit_type_cat'] == 'FRSH')][[
                            'emplid',
							# 'enrl_ind', 
							# 'acad_year',
							# 'age_group', 
							# 'age',
							'male',
							# 'race_hispanic',
							# 'race_american_indian',
							# 'race_alaska',
							# 'race_asian',
							# 'race_black',
							# 'race_native_hawaiian',
							# 'race_white',
							# 'min_week_from_term_begin_dt',
							# 'max_week_from_term_begin_dt',
							'count_week_from_term_begin_dt',
							# 'marital_status',
							'acs_mi',
							'distance',
							'pop_dens',
							'underrep_minority', 
							# 'ipeds_ethnic_group_descrshort',
							'pell_eligibility_ind',
							# 'pell_recipient_ind',
							'first_gen_flag',
							'first_gen_flag_mi', 
							# 'LSAMP_STEM_Flag',
							# 'anywhere_STEM_Flag',
							# 'honors_program_ind',
							# 'afl_greek_indicator',
							'high_school_gpa',
							'high_school_gpa_mi',
							'fall_midterm_gpa_avg',
							'fall_midterm_gpa_avg_mi',
							'fall_midterm_grade_count',
							# 'fall_midterm_S_grade_count',
							# 'fall_midterm_W_grade_count',
							# 'awe_instrument',
							# 'cdi_instrument',
							'fall_avg_difficulty',
							'fall_avg_pct_withdrawn',
							# 'fall_avg_pct_CDFW',
							'fall_avg_pct_CDF',
							# 'fall_avg_pct_DFW',
							# 'fall_avg_pct_DF',
							# 'fall_crse_mi',
							'fall_lec_count',
							'fall_lab_count',
							# 'fall_int_count',
							# 'fall_stu_count',
							# 'fall_sem_count',
							# 'fall_oth_count',
							# 'fall_lec_contact_hrs',
							# 'fall_lab_contact_hrs',
							# 'fall_int_contact_hrs',
							# 'fall_stu_contact_hrs',
							# 'fall_sem_contact_hrs',
							# 'fall_oth_contact_hrs',
							# 'total_fall_contact_hrs',
							'cum_adj_transfer_hours',
							'resident',
							# 'father_wsu_flag',
							# 'mother_wsu_flag',
							'parent1_highest_educ_lvl',
							'parent2_highest_educ_lvl',
							# 'citizenship_country',
							'gini_indx',
							'pvrt_rate',
							'median_inc',
							'median_value',
							'educ_rate',
							'pct_blk',
							'pct_ai',
							'pct_asn',
							'pct_hawi',
							'pct_oth',
							'pct_two',
							# 'pct_non',
							'pct_hisp',
							# 'city_large',
							# 'city_mid',
							# 'city_small',
							# 'suburb_large',
							# 'suburb_mid',
							# 'suburb_small',
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
							'fall_credit_hours',
							# 'total_fall_units',
							'fall_withdrawn_hours',
							# 'fall_withdrawn_ind',
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
							'unmet_need_ofr',
							'unmet_need_ofr_mi'
                            ]].dropna()

vanco_testing_set = vanco_testing_set.reset_index()

vanco_shap_outcome = vanco_testing_set['emplid'].copy(deep=True).values.tolist()

vanco_pred_outcome = vanco_testing_set[[ 
                            'emplid',
                            # 'enrl_ind'
                            ]].copy(deep=True)

vanco_aggregate_outcome = vanco_testing_set[[ 
                            'emplid',
							'male',
							'underrep_minority',
							'first_gen_flag',
							'resident'
                            # 'enrl_ind'
                            ]].copy(deep=True)

vanco_current_outcome = vanco_testing_set[[ 
                            'emplid',
                            # 'enrl_ind'
                            ]].copy(deep=True)

#%%
# Tri-Cities dataframes
trici_logit_df = training_set[(training_set['adj_acad_prog_primary_campus'] == 'TRICI') & (training_set['adj_admit_type_cat'] == 'FRSH')][[
                        'enrl_ind', 
                        # 'acad_year',
						# 'age_group', 
						# 'age',
						'male',
						# 'race_hispanic',
						# 'race_american_indian',
						# 'race_alaska',
						# 'race_asian',
						# 'race_black',
						# 'race_native_hawaiian',
						# 'race_white',
						# 'min_week_from_term_begin_dt',
						# 'max_week_from_term_begin_dt',
						'count_week_from_term_begin_dt',
						# 'marital_status',
						'acs_mi',
						'distance',
						'pop_dens',
						'underrep_minority', 
						# 'ipeds_ethnic_group_descrshort',
						'pell_eligibility_ind',
						# 'pell_recipient_ind',
						'first_gen_flag',
						'first_gen_flag_mi', 
						# 'LSAMP_STEM_Flag',
						# 'anywhere_STEM_Flag',
						# 'honors_program_ind',
						# 'afl_greek_indicator',
						'high_school_gpa',
						'high_school_gpa_mi',
						'fall_midterm_gpa_avg',
						'fall_midterm_gpa_avg_mi',
						'fall_midterm_grade_count',
						# 'fall_midterm_S_grade_count',
						# 'fall_midterm_W_grade_count',
						# 'awe_instrument',
						# 'cdi_instrument',
						'fall_avg_difficulty',
						'fall_avg_pct_withdrawn',
						# 'fall_avg_pct_CDFW',
						'fall_avg_pct_CDF',
						# 'fall_avg_pct_DFW',
						# 'fall_avg_pct_DF',
						# 'fall_crse_mi',
						'fall_lec_count',
						'fall_lab_count',
						# 'fall_int_count',
						# 'fall_stu_count',
						# 'fall_sem_count',
						# 'fall_oth_count',
						# 'fall_lec_contact_hrs',
						# 'fall_lab_contact_hrs',
						# 'fall_int_contact_hrs',
						# 'fall_stu_contact_hrs',
						# 'fall_sem_contact_hrs',
						# 'fall_oth_contact_hrs',
						# 'total_fall_contact_hrs',
						'cum_adj_transfer_hours',
						'resident',
						# 'father_wsu_flag',
						# 'mother_wsu_flag',
						'parent1_highest_educ_lvl',
						'parent2_highest_educ_lvl',
						# 'citizenship_country',
						'gini_indx',
						'pvrt_rate',
						'median_inc',
						'median_value',
						'educ_rate',
						'pct_blk',
						'pct_ai',
						'pct_asn',
						'pct_hawi',
						'pct_oth',
						'pct_two',
						# 'pct_non',
						'pct_hisp',
						# 'city_large',
						# 'city_mid',
						# 'city_small',
						# 'suburb_large',
						# 'suburb_mid',
						# 'suburb_small',
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
						'fall_credit_hours',
						# 'total_fall_units',
						'fall_withdrawn_hours',
						# 'fall_withdrawn_ind',
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
						'unmet_need_ofr',
						'unmet_need_ofr_mi'
                        ]].dropna()

trici_training_set = training_set[(training_set['adj_acad_prog_primary_campus'] == 'TRICI') & (training_set['adj_admit_type_cat'] == 'FRSH')][[
                            'emplid',
                            'enrl_ind', 
							# 'acad_year',
							# 'age_group', 
							# 'age',
							'male',
							# 'race_hispanic',
							# 'race_american_indian',
							# 'race_alaska',
							# 'race_asian',
							# 'race_black',
							# 'race_native_hawaiian',
							# 'race_white',
							# 'min_week_from_term_begin_dt',
							# 'max_week_from_term_begin_dt',
							'count_week_from_term_begin_dt',
							# 'marital_status',
							'acs_mi',
							'distance',
							'pop_dens',
							'underrep_minority', 
							# 'ipeds_ethnic_group_descrshort',
							'pell_eligibility_ind',
							# 'pell_recipient_ind',
							'first_gen_flag',
							'first_gen_flag_mi', 
							# 'LSAMP_STEM_Flag',
							# 'anywhere_STEM_Flag',
							# 'honors_program_ind',
							# 'afl_greek_indicator',
							'high_school_gpa',
							'high_school_gpa_mi',
							'fall_midterm_gpa_avg',
							'fall_midterm_gpa_avg_mi',
							'fall_midterm_grade_count',
							# 'fall_midterm_S_grade_count',
							# 'fall_midterm_W_grade_count',
							# 'awe_instrument',
							# 'cdi_instrument',
							'fall_avg_difficulty',
							'fall_avg_pct_withdrawn',
							# 'fall_avg_pct_CDFW',
							'fall_avg_pct_CDF',
							# 'fall_avg_pct_DFW',
							# 'fall_avg_pct_DF',
							# 'fall_crse_mi',
							'fall_lec_count',
							'fall_lab_count',
							# 'fall_int_count',
							# 'fall_stu_count',
							# 'fall_sem_count',
							# 'fall_oth_count',
							# 'fall_lec_contact_hrs',
							# 'fall_lab_contact_hrs',
							# 'fall_int_contact_hrs',
							# 'fall_stu_contact_hrs',
							# 'fall_sem_contact_hrs',
							# 'fall_oth_contact_hrs',
							# 'total_fall_contact_hrs',
							'cum_adj_transfer_hours',
							'resident',
							# 'father_wsu_flag',
							# 'mother_wsu_flag',
							'parent1_highest_educ_lvl',
							'parent2_highest_educ_lvl',
							# 'citizenship_country',
							'gini_indx',
							'pvrt_rate',
							'median_inc',
							'median_value',
							'educ_rate',
							'pct_blk',
							'pct_ai',
							'pct_asn',
							'pct_hawi',
							'pct_oth',
							'pct_two',
							# 'pct_non',
							'pct_hisp',
							# 'city_large',
							# 'city_mid',
							# 'city_small',
							# 'suburb_large',
							# 'suburb_mid',
							# 'suburb_small',
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
							'fall_credit_hours',
							# 'total_fall_units',
							'fall_withdrawn_hours',
							# 'fall_withdrawn_ind',
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
							'unmet_need_ofr',
							'unmet_need_ofr_mi'
                            ]].dropna()

trici_testing_set = testing_set[(testing_set['adj_acad_prog_primary_campus'] == 'TRICI') & (testing_set['adj_admit_type_cat'] == 'FRSH')][[
                            'emplid',
							# 'enrl_ind', 
							# 'acad_year',
							# 'age_group', 
							# 'age',
							'male',
							# 'race_hispanic',
							# 'race_american_indian',
							# 'race_alaska',
							# 'race_asian',
							# 'race_black',
							# 'race_native_hawaiian',
							# 'race_white',
							# 'min_week_from_term_begin_dt',
							# 'max_week_from_term_begin_dt',
							'count_week_from_term_begin_dt',
							# 'marital_status',
							'acs_mi',
							'distance',
							'pop_dens',
							'underrep_minority', 
							# 'ipeds_ethnic_group_descrshort',
							'pell_eligibility_ind',
							# 'pell_recipient_ind',
							'first_gen_flag',
							'first_gen_flag_mi', 
							# 'LSAMP_STEM_Flag',
							# 'anywhere_STEM_Flag',
							# 'honors_program_ind',
							# 'afl_greek_indicator',
							'high_school_gpa',
							'high_school_gpa_mi',
							'fall_midterm_gpa_avg',
							'fall_midterm_gpa_avg_mi',
							'fall_midterm_grade_count',
							# 'fall_midterm_S_grade_count',
							# 'fall_midterm_W_grade_count',
							# 'awe_instrument',
							# 'cdi_instrument',
							'fall_avg_difficulty',
							'fall_avg_pct_withdrawn',
							# 'fall_avg_pct_CDFW',
							'fall_avg_pct_CDF',
							# 'fall_avg_pct_DFW',
							# 'fall_avg_pct_DF',
							# 'fall_crse_mi',
							'fall_lec_count',
							'fall_lab_count',
							# 'fall_int_count',
							# 'fall_stu_count',
							# 'fall_sem_count',
							# 'fall_oth_count',
							# 'fall_lec_contact_hrs',
							# 'fall_lab_contact_hrs',
							# 'fall_int_contact_hrs',
							# 'fall_stu_contact_hrs',
							# 'fall_sem_contact_hrs',
							# 'fall_oth_contact_hrs',
							# 'total_fall_contact_hrs',
							'cum_adj_transfer_hours',
							'resident',
							# 'father_wsu_flag',
							# 'mother_wsu_flag',
							'parent1_highest_educ_lvl',
							'parent2_highest_educ_lvl',
							# 'citizenship_country',
							'gini_indx',
							'pvrt_rate',
							'median_inc',
							'median_value',
							'educ_rate',
							'pct_blk',
							'pct_ai',
							'pct_asn',
							'pct_hawi',
							'pct_oth',
							'pct_two',
							# 'pct_non',
							'pct_hisp',
							# 'city_large',
							# 'city_mid',
							# 'city_small',
							# 'suburb_large',
							# 'suburb_mid',
							# 'suburb_small',
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
							'fall_credit_hours',
							# 'total_fall_units',
							'fall_withdrawn_hours',
							# 'fall_withdrawn_ind',
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
							'unmet_need_ofr',
							'unmet_need_ofr_mi'
                            ]].dropna()

trici_testing_set = trici_testing_set.reset_index()

trici_shap_outcome = trici_testing_set['emplid'].copy(deep=True).values.tolist()

trici_pred_outcome = trici_testing_set[[ 
                            'emplid',
                            # 'enrl_ind'
                            ]].copy(deep=True)

trici_aggregate_outcome = trici_testing_set[[ 
                            'emplid',
							'male',
							'underrep_minority',
							'first_gen_flag',
							'resident'
                            # 'enrl_ind'
                            ]].copy(deep=True)

trici_current_outcome = trici_testing_set[[ 
                            'emplid',
                            # 'enrl_ind'
                            ]].copy(deep=True)

#%%
# University dataframes
univr_logit_df = training_set[(training_set['adj_admit_type_cat'] == 'FRSH')][[
                        'enrl_ind', 
                        # 'acad_year',
						# 'age_group', 
						# 'age',
						'male',
						# 'race_hispanic',
						# 'race_american_indian',
						# 'race_alaska',
						# 'race_asian',
						# 'race_black',
						# 'race_native_hawaiian',
						# 'race_white',
						# 'min_week_from_term_begin_dt',
						# 'max_week_from_term_begin_dt',
						'count_week_from_term_begin_dt',
						# 'marital_status',
						'acs_mi',
						'distance',
						'pop_dens',
						'underrep_minority', 
						# 'ipeds_ethnic_group_descrshort',
						'pell_eligibility_ind',
						# 'pell_recipient_ind',
						'first_gen_flag',
						'first_gen_flag_mi', 
						# 'LSAMP_STEM_Flag',
						# 'anywhere_STEM_Flag',
						# 'honors_program_ind',
						# 'afl_greek_indicator',
						'high_school_gpa',
						'high_school_gpa_mi',
						'fall_midterm_gpa_avg',
						'fall_midterm_gpa_avg_mi',
						'fall_midterm_grade_count',
						'fall_midterm_S_grade_count',
						'fall_midterm_W_grade_count',
						# 'awe_instrument',
						# 'cdi_instrument',
						'fall_avg_difficulty',
						'fall_avg_pct_withdrawn',
						# 'fall_avg_pct_CDFW',
						'fall_avg_pct_CDF',
						# 'fall_avg_pct_DFW',
						# 'fall_avg_pct_DF',
						# 'fall_crse_mi',
						'fall_lec_count',
						'fall_lab_count',
						# 'fall_int_count',
						# 'fall_stu_count',
						# 'fall_sem_count',
						# 'fall_oth_count',
						# 'fall_lec_contact_hrs',
						# 'fall_lab_contact_hrs',
						# 'fall_int_contact_hrs',
						# 'fall_stu_contact_hrs',
						# 'fall_sem_contact_hrs',
						# 'fall_oth_contact_hrs',
						# 'total_fall_contact_hrs',
						'cum_adj_transfer_hours',
						'resident',
						# 'father_wsu_flag',
						# 'mother_wsu_flag',
						'parent1_highest_educ_lvl',
						'parent2_highest_educ_lvl',
						# 'citizenship_country',
						'gini_indx',
						'pvrt_rate',
						'median_inc',
						'median_value',
						'educ_rate',
						'pct_blk',
						'pct_ai',
						'pct_asn',
						'pct_hawi',
						'pct_oth',
						'pct_two',
						# 'pct_non',
						'pct_hisp',
						# 'city_large',
						# 'city_mid',
						# 'city_small',
						# 'suburb_large',
						# 'suburb_mid',
						# 'suburb_small',
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
						'fall_credit_hours',
						# 'total_fall_units',
						'fall_withdrawn_hours',
						# 'fall_withdrawn_ind',
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
						'unmet_need_ofr',
						'unmet_need_ofr_mi'
                        ]].dropna()

univr_training_set = training_set[(training_set['adj_admit_type_cat'] == 'FRSH')][[
                            'emplid',
                            'enrl_ind', 
							# 'acad_year',
							# 'age_group', 
							# 'age',
							'male',
							# 'race_hispanic',
							# 'race_american_indian',
							# 'race_alaska',
							# 'race_asian',
							# 'race_black',
							# 'race_native_hawaiian',
							# 'race_white',
							# 'min_week_from_term_begin_dt',
							# 'max_week_from_term_begin_dt',
							'count_week_from_term_begin_dt',
							# 'marital_status',
							'acs_mi',
							'distance',
							'pop_dens',
							'underrep_minority', 
							# 'ipeds_ethnic_group_descrshort',
							'pell_eligibility_ind',
							# 'pell_recipient_ind',
							'first_gen_flag',
							'first_gen_flag_mi', 
							# 'LSAMP_STEM_Flag',
							# 'anywhere_STEM_Flag',
							# 'honors_program_ind',
							# 'afl_greek_indicator',
							'high_school_gpa',
							'high_school_gpa_mi',
							'fall_midterm_gpa_avg',
							'fall_midterm_gpa_avg_mi',
							'fall_midterm_grade_count',
							'fall_midterm_S_grade_count',
							'fall_midterm_W_grade_count',
							# 'awe_instrument',
							# 'cdi_instrument',
							'fall_avg_difficulty',
							'fall_avg_pct_withdrawn',
							# 'fall_avg_pct_CDFW',
							'fall_avg_pct_CDF',
							# 'fall_avg_pct_DFW',
							# 'fall_avg_pct_DF',
							# 'fall_crse_mi',
							'fall_lec_count',
							'fall_lab_count',
							# 'fall_int_count',
							# 'fall_stu_count',
							# 'fall_sem_count',
							# 'fall_oth_count',
							# 'fall_lec_contact_hrs',
							# 'fall_lab_contact_hrs',
							# 'fall_int_contact_hrs',
							# 'fall_stu_contact_hrs',
							# 'fall_sem_contact_hrs',
							# 'fall_oth_contact_hrs',
							# 'total_fall_contact_hrs',
							'cum_adj_transfer_hours',
							'resident',
							# 'father_wsu_flag',
							# 'mother_wsu_flag',
							'parent1_highest_educ_lvl',
							'parent2_highest_educ_lvl',
							# 'citizenship_country',
							'gini_indx',
							'pvrt_rate',
							'median_inc',
							'median_value',
							'educ_rate',
							'pct_blk',
							'pct_ai',
							'pct_asn',
							'pct_hawi',
							'pct_oth',
							'pct_two',
							# 'pct_non',
							'pct_hisp',
							# 'city_large',
							# 'city_mid',
							# 'city_small',
							# 'suburb_large',
							# 'suburb_mid',
							# 'suburb_small',
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
							'fall_credit_hours',
							# 'total_fall_units',
							'fall_withdrawn_hours',
							# 'fall_withdrawn_ind',
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
							'unmet_need_ofr',
							'unmet_need_ofr_mi'
                            ]].dropna()

univr_testing_set = testing_set[((testing_set['adj_acad_prog_primary_campus'] == 'EVERE') & (testing_set['adj_admit_type_cat'] == 'FRSH')) | ((testing_set['adj_acad_prog_primary_campus'] == 'SPOKA') & (testing_set['adj_admit_type_cat'] == 'FRSH')) | ((testing_set['adj_acad_prog_primary_campus'] == 'ONLIN') & (testing_set['adj_admit_type_cat'] == 'FRSH'))][[
                            'emplid',
							# 'enrl_ind', 
							# 'acad_year',
							# 'age_group', 
							# 'age',
							'male',
							# 'race_hispanic',
							# 'race_american_indian',
							# 'race_alaska',
							# 'race_asian',
							# 'race_black',
							# 'race_native_hawaiian',
							# 'race_white',
							# 'min_week_from_term_begin_dt',
							# 'max_week_from_term_begin_dt',
							'count_week_from_term_begin_dt',
							# 'marital_status',
							'acs_mi',
							'distance',
							'pop_dens',
							'underrep_minority', 
							# 'ipeds_ethnic_group_descrshort',
							'pell_eligibility_ind',
							# 'pell_recipient_ind',
							'first_gen_flag',
							'first_gen_flag_mi', 
							# 'LSAMP_STEM_Flag',
							# 'anywhere_STEM_Flag',
							# 'honors_program_ind',
							# 'afl_greek_indicator',
							'high_school_gpa',
							'high_school_gpa_mi',
							'fall_midterm_gpa_avg',
							'fall_midterm_gpa_avg_mi',
							'fall_midterm_grade_count',
							'fall_midterm_S_grade_count',
							'fall_midterm_W_grade_count',
							# 'awe_instrument',
							# 'cdi_instrument',
							'fall_avg_difficulty',
							'fall_avg_pct_withdrawn',
							# 'fall_avg_pct_CDFW',
							'fall_avg_pct_CDF',
							# 'fall_avg_pct_DFW',
							# 'fall_avg_pct_DF',
							# 'fall_crse_mi',
							'fall_lec_count',
							'fall_lab_count',
							# 'fall_int_count',
							# 'fall_stu_count',
							# 'fall_sem_count',
							# 'fall_oth_count',
							# 'fall_lec_contact_hrs',
							# 'fall_lab_contact_hrs',
							# 'fall_int_contact_hrs',
							# 'fall_stu_contact_hrs',
							# 'fall_sem_contact_hrs',
							# 'fall_oth_contact_hrs',
							# 'total_fall_contact_hrs',
							'cum_adj_transfer_hours',
							'resident',
							# 'father_wsu_flag',
							# 'mother_wsu_flag',
							'parent1_highest_educ_lvl',
							'parent2_highest_educ_lvl',
							# 'citizenship_country',
							'gini_indx',
							'pvrt_rate',
							'median_inc',
							'median_value',
							'educ_rate',
							'pct_blk',
							'pct_ai',
							'pct_asn',
							'pct_hawi',
							'pct_oth',
							'pct_two',
							# 'pct_non',
							'pct_hisp',
							# 'city_large',
							# 'city_mid',
							# 'city_small',
							# 'suburb_large',
							# 'suburb_mid',
							# 'suburb_small',
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
							'fall_credit_hours',
							# 'total_fall_units',
							'fall_withdrawn_hours',
							# 'fall_withdrawn_ind',
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
							'unmet_need_ofr',
							'unmet_need_ofr_mi'
                            ]].dropna()

univr_testing_set = univr_testing_set.reset_index()

univr_shap_outcome = univr_testing_set['emplid'].copy(deep=True).values.tolist()

univr_pred_outcome = univr_testing_set[[ 
                            'emplid',
                            # 'enrl_ind'
                            ]].copy(deep=True)

univr_aggregate_outcome = univr_testing_set[[ 
                            'emplid',
							'male',
							'underrep_minority',
							'first_gen_flag',
							'resident'
                            # 'enrl_ind'
                            ]].copy(deep=True)

univr_current_outcome = univr_testing_set[[ 
                            'emplid',
                            # 'enrl_ind'
                            ]].copy(deep=True)

#%%
# Detect and remove outliers
print('\nDetect and remove outliers...')

# Pullman outliers
pullm_x_outlier = pullm_training_set.drop(columns=['enrl_ind','emplid'])

pullm_outlier_prep = make_column_transformer(
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

pullm_x_outlier = pullm_outlier_prep.fit_transform(pullm_x_outlier)

pullm_training_set['mask'] = LocalOutlierFactor(metric='manhattan', n_jobs=-1).fit_predict(pullm_x_outlier)

pullm_outlier_set = pullm_training_set.drop(pullm_training_set[pullm_training_set['mask'] == 1].index)
pullm_outlier_set.to_csv('Z:\\Nathan\\Models\\student_risk\\outliers\\pullm_frsh_outlier_set.csv', encoding='utf-8', index=False)

pullm_training_set = pullm_training_set.drop(pullm_training_set[pullm_training_set['mask'] == -1].index)
pullm_training_set = pullm_training_set.drop(columns='mask')

#%%
# Vancouver outliers
vanco_x_outlier = vanco_training_set.drop(columns=['enrl_ind','emplid'])

vanco_outlier_prep = make_column_transformer(
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

vanco_x_outlier = vanco_outlier_prep.fit_transform(vanco_x_outlier)

vanco_training_set['mask'] = LocalOutlierFactor(metric='manhattan', n_jobs=-1).fit_predict(vanco_x_outlier)

vanco_outlier_set = vanco_training_set.drop(vanco_training_set[vanco_training_set['mask'] == 1].index)
vanco_outlier_set.to_csv('Z:\\Nathan\\Models\\student_risk\\outliers\\vanco_frsh_outlier_set.csv', encoding='utf-8', index=False)

vanco_training_set = vanco_training_set.drop(vanco_training_set[vanco_training_set['mask'] == -1].index)
vanco_training_set = vanco_training_set.drop(columns='mask')

#%%
# Tri-Cities outliers
trici_x_outlier = trici_training_set.drop(columns=['enrl_ind','emplid'])

trici_outlier_prep = make_column_transformer(
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

trici_x_outlier = trici_outlier_prep.fit_transform(trici_x_outlier)

trici_training_set['mask'] = LocalOutlierFactor(metric='manhattan', n_jobs=-1).fit_predict(trici_x_outlier)

trici_outlier_set = trici_training_set.drop(trici_training_set[trici_training_set['mask'] == 1].index)
trici_outlier_set.to_csv('Z:\\Nathan\\Models\\student_risk\\outliers\\trici_frsh_outlier_set.csv', encoding='utf-8', index=False)

trici_training_set = trici_training_set.drop(trici_training_set[trici_training_set['mask'] == -1].index)
trici_training_set = trici_training_set.drop(columns='mask')

#%%
# University outliers
univr_x_outlier = univr_training_set.drop(columns=['enrl_ind','emplid'])

univr_outlier_prep = make_column_transformer(
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

univr_x_outlier = univr_outlier_prep.fit_transform(univr_x_outlier)

univr_training_set['mask'] = LocalOutlierFactor(metric='manhattan', n_jobs=-1).fit_predict(univr_x_outlier)

univr_outlier_set = univr_training_set.drop(univr_training_set[univr_training_set['mask'] == 1].index)
univr_outlier_set.to_csv('Z:\\Nathan\\Models\\student_risk\\outliers\\univr_frsh_outlier_set.csv', encoding='utf-8', index=False)

univr_training_set = univr_training_set.drop(univr_training_set[univr_training_set['mask'] == -1].index)
univr_training_set = univr_training_set.drop(columns='mask')

#%%
# Create Tomek Link undersampled training set

# Pullman undersample
pullm_x_train = pullm_training_set.drop(columns=['enrl_ind','emplid'])

pullm_x_test = pullm_testing_set[[
						# 'acad_year',
						# 'age_group', 
						# 'age',
						'male',
						# 'race_hispanic',
						# 'race_american_indian',
						# 'race_alaska',
						# 'race_asian',
						# 'race_black',
						# 'race_native_hawaiian',
						# 'race_white',
						# 'min_week_from_term_begin_dt',
						# 'max_week_from_term_begin_dt',
						'count_week_from_term_begin_dt',
						# 'marital_status',
						'acs_mi',
						'distance',
						'pop_dens',
						'underrep_minority', 
						# 'ipeds_ethnic_group_descrshort',
						'pell_eligibility_ind',
						# 'pell_recipient_ind',
						'first_gen_flag',
						'first_gen_flag_mi', 
						# 'LSAMP_STEM_Flag',
						# 'anywhere_STEM_Flag',
						'honors_program_ind',
						# 'afl_greek_indicator',
						'high_school_gpa',
						'high_school_gpa_mi',
						'fall_midterm_gpa_avg',
						'fall_midterm_gpa_avg_mi',
						'fall_midterm_grade_count',
						'fall_midterm_S_grade_count',
						'fall_midterm_W_grade_count',
						# 'awe_instrument',
						# 'cdi_instrument',
						'fall_avg_difficulty',
						'fall_avg_pct_withdrawn',
						# 'fall_avg_pct_CDFW',
						'fall_avg_pct_CDF',
						# 'fall_avg_pct_DFW',
						# 'fall_avg_pct_DF',
						# 'fall_crse_mi',
						'fall_lec_count',
						'fall_lab_count',
						# 'fall_int_count',
						'fall_stu_count',
						# 'fall_sem_count',
						'fall_oth_count',
						# 'fall_lec_contact_hrs',
						# 'fall_lab_contact_hrs',
						# 'fall_int_contact_hrs',
						# 'fall_stu_contact_hrs',
						# 'fall_sem_contact_hrs',
						# 'fall_oth_contact_hrs',
						# 'total_fall_contact_hrs',
						'cum_adj_transfer_hours',
						'resident',
						# 'father_wsu_flag',
						# 'mother_wsu_flag',
						'parent1_highest_educ_lvl',
						'parent2_highest_educ_lvl',
						# 'citizenship_country',
						'gini_indx',
						'pvrt_rate',
						'median_inc',
						'median_value',
						'educ_rate',
						'pct_blk',
						'pct_ai',
						'pct_asn',
						'pct_hawi',
						'pct_oth',
						'pct_two',
						# 'pct_non',
						'pct_hisp',
						# 'city_large',
						# 'city_mid',
						# 'city_small',
						# 'suburb_large',
						# 'suburb_mid',
						# 'suburb_small',
						# 'town_fringe',
						# 'town_distant',
						# 'town_remote',
						# 'rural_fringe',
						# 'rural_distant',
						# 'rural_remote',
						'AD_DTA',
						'AD_AST',
						'AP',
						'RS',
						'CHS',
						# 'IB',
						# 'AICE',
						'IB_AICE', 
						'fall_credit_hours',
						# 'total_fall_units',
						'fall_withdrawn_hours',
						# 'fall_withdrawn_ind',
						# 'athlete',
						'remedial',
						# 'ACAD_PLAN',
						# 'plan_owner_org',
						'business',
						'cahnrs_anml',
						# 'cahnrs_envr',
						'cahnrs_econ',
						'cahnrext',
						'cas_chem',
						'cas_crim',
						'cas_math',
						'cas_psyc',
						'cas_biol',
						'cas_engl',
						'cas_phys',
						'cas',
						'comm',
						'education',
						'medicine',
						'nursing',
						# 'pharmacy',
						# 'provost',
						'vcea_bioe',
						'vcea_cive',
						'vcea_desn',
						'vcea_eecs',
						'vcea_mech',
						'vcea',
						'vet_med',
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
						'unmet_need_ofr',
						'unmet_need_ofr_mi'
                        ]]

pullm_y_train = pullm_training_set['enrl_ind']
# pullm_y_test = pullm_testing_set['enrl_ind']

pullm_tomek_prep = make_column_transformer(
	(StandardScaler(), [
						'distance',
						# 'age',
						# 'min_week_from_term_begin_dt',
						# 'max_week_from_term_begin_dt',
						'count_week_from_term_begin_dt',
						# 'sat_erws',
						# 'sat_mss',
						# 'sat_comp',
						# 'attendee_total_visits',
						'pop_dens', 
						# 'qvalue', 
						# 'gini_indx',
						'median_inc',
						# 'pvrt_rate',
						'median_value',
						# 'educ_rate',
						# 'pct_blk',
						# 'pct_ai',
						# 'pct_asn',
						# 'pct_hawi',
						# 'pct_oth',
						# 'pct_two',
						# 'pct_non',
						# 'pct_hisp',
						'high_school_gpa',
						'fall_midterm_gpa_avg',
						'fall_midterm_grade_count',
						'fall_midterm_S_grade_count',
						'fall_midterm_W_grade_count',
						# 'awe_instrument',
						# 'cdi_instrument',
						'fall_avg_difficulty',
						# 'fall_avg_pct_withdrawn',
						# 'fall_avg_pct_CDFW',
						# 'fall_avg_pct_CDF',
						'fall_lec_count',
						'fall_lab_count',
						# 'fall_int_count',
						'fall_stu_count',
						# 'fall_sem_count',
						'fall_oth_count',
						# 'fall_lec_contact_hrs',
						# 'fall_lab_contact_hrs',
						# 'fall_int_contact_hrs',
						# 'fall_stu_contact_hrs',
						# 'fall_sem_contact_hrs',
						# 'fall_oth_contact_hrs',
						# 'total_fall_contact_hrs',
						# 'total_fall_units',
						'fall_credit_hours',
						'fall_withdrawn_hours',
						'cum_adj_transfer_hours',
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

pullm_x_train = pullm_tomek_prep.fit_transform(pullm_x_train)
pullm_x_test = pullm_tomek_prep.transform(pullm_x_test)

pullm_feat_names = []

for name, transformer, features, _ in pullm_tomek_prep._iter(fitted=True):

	if transformer != 'passthrough':
		try:
			pullm_feat_names.extend(pullm_tomek_prep.named_transformers_[name].get_feature_names())
		except AttributeError:
			pullm_feat_names.extend(features)

	if transformer == 'passthrough':
		pullm_feat_names.extend(pullm_tomek_prep._feature_names_in[features])

pullm_under = TomekLinks(sampling_strategy='all', n_jobs=-1)
pullm_x_train, pullm_y_train = pullm_under.fit_resample(pullm_x_train, pullm_y_train)

pullm_tomek_index = pullm_under.sample_indices_
pullm_training_set = pullm_training_set.reset_index(drop=True)

pullm_tomek_set = pullm_training_set.drop(pullm_tomek_index)
pullm_tomek_set.to_csv('Z:\\Nathan\\Models\\student_risk\\outliers\\pullm_frsh_tomek_set.csv', encoding='utf-8', index=False)

#%%
# Vancouver undersample
vanco_x_train = vanco_training_set.drop(columns=['enrl_ind','emplid'])

vanco_x_test = vanco_testing_set[[
                        # 'acad_year',
						# 'age_group', 
						# 'age',
						'male',
						# 'race_hispanic',
						# 'race_american_indian',
						# 'race_alaska',
						# 'race_asian',
						# 'race_black',
						# 'race_native_hawaiian',
						# 'race_white',
						# 'min_week_from_term_begin_dt',
						# 'max_week_from_term_begin_dt',
						'count_week_from_term_begin_dt',
						# 'marital_status',
						'acs_mi',
						'distance',
						'pop_dens',
						'underrep_minority', 
						# 'ipeds_ethnic_group_descrshort',
						'pell_eligibility_ind',
						# 'pell_recipient_ind',
						'first_gen_flag',
						'first_gen_flag_mi', 
						# 'LSAMP_STEM_Flag',
						# 'anywhere_STEM_Flag',
						# 'honors_program_ind',
						# 'afl_greek_indicator',
						'high_school_gpa',
						'high_school_gpa_mi',
						'fall_midterm_gpa_avg',
						'fall_midterm_gpa_avg_mi',
						'fall_midterm_grade_count',
						# 'fall_midterm_S_grade_count',
						# 'fall_midterm_W_grade_count',
						# 'awe_instrument',
						# 'cdi_instrument',
						'fall_avg_difficulty',
						'fall_avg_pct_withdrawn',
						# 'fall_avg_pct_CDFW',
						'fall_avg_pct_CDF',
						# 'fall_avg_pct_DFW',
						# 'fall_avg_pct_DF',
						# 'fall_crse_mi',
						'fall_lec_count',
						'fall_lab_count',
						# 'fall_int_count',
						# 'fall_stu_count',
						# 'fall_sem_count',
						# 'fall_oth_count',
						# 'fall_lec_contact_hrs',
						# 'fall_lab_contact_hrs',
						# 'fall_int_contact_hrs',
						# 'fall_stu_contact_hrs',
						# 'fall_sem_contact_hrs',
						# 'fall_oth_contact_hrs',
						# 'total_fall_contact_hrs',
						'cum_adj_transfer_hours',
						'resident',
						# 'father_wsu_flag',
						# 'mother_wsu_flag',
						'parent1_highest_educ_lvl',
						'parent2_highest_educ_lvl',
						# 'citizenship_country',
						'gini_indx',
						'pvrt_rate',
						'median_inc',
						'median_value',
						'educ_rate',
						'pct_blk',
						'pct_ai',
						'pct_asn',
						'pct_hawi',
						'pct_oth',
						'pct_two',
						# 'pct_non',
						'pct_hisp',
						# 'city_large',
						# 'city_mid',
						# 'city_small',
						# 'suburb_large',
						# 'suburb_mid',
						# 'suburb_small',
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
						'fall_credit_hours',
						# 'total_fall_units',
						'fall_withdrawn_hours',
						# 'fall_withdrawn_ind',
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
						'unmet_need_ofr',
						'unmet_need_ofr_mi'
                        ]]

vanco_y_train = vanco_training_set['enrl_ind']
# vanco_y_test = vanco_testing_set['enrl_ind']

vanco_tomek_prep = make_column_transformer(
	(StandardScaler(), [
						'distance',
						# 'age',
						# 'min_week_from_term_begin_dt',
						# 'max_week_from_term_begin_dt',
						'count_week_from_term_begin_dt',
						# 'sat_erws',
						# 'sat_mss',
						# 'sat_comp',
						# 'attendee_total_visits',
						'pop_dens', 
						# 'qvalue', 
						# 'gini_indx',
						'median_inc',
						# 'pvrt_rate',
						'median_value',
						# 'educ_rate',
						# 'pct_blk',
						# 'pct_ai',
						# 'pct_asn',
						# 'pct_hawi',
						# 'pct_oth',
						# 'pct_two',
						# 'pct_non',
						# 'pct_hisp',
						'high_school_gpa',
						'fall_midterm_gpa_avg',
						'fall_midterm_grade_count',
						# 'fall_midterm_S_grade_count',
						# 'fall_midterm_W_grade_count',
						# 'awe_instrument',
						# 'cdi_instrument',
						'fall_avg_difficulty',
						# 'fall_avg_pct_withdrawn',
						# 'fall_avg_pct_CDFW',
						# 'fall_avg_pct_CDF',
						'fall_lec_count',
						'fall_lab_count',
						# 'fall_int_count',
						# 'fall_stu_count',
						# 'fall_sem_count',
						# 'fall_oth_count',
						# 'fall_lec_contact_hrs',
						# 'fall_lab_contact_hrs',
						# 'fall_int_contact_hrs',
						# 'fall_stu_contact_hrs',
						# 'fall_sem_contact_hrs',
						# 'fall_oth_contact_hrs',
						# 'total_fall_contact_hrs',
						# 'total_fall_units',
						'fall_credit_hours',
						'fall_withdrawn_hours',
						'cum_adj_transfer_hours',
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

vanco_x_train = vanco_tomek_prep.fit_transform(vanco_x_train)
vanco_x_test = vanco_tomek_prep.transform(vanco_x_test)

vanco_feat_names = []

for name, transformer, features, _ in vanco_tomek_prep._iter(fitted=True):

	if transformer != 'passthrough':
		try:
			vanco_feat_names.extend(vanco_tomek_prep.named_transformers_[name].get_feature_names())
		except AttributeError:
			vanco_feat_names.extend(features)

	if transformer == 'passthrough':
		vanco_feat_names.extend(vanco_tomek_prep._feature_names_in[features])

vanco_under = TomekLinks(sampling_strategy='all', n_jobs=-1)
vanco_x_train, vanco_y_train = vanco_under.fit_resample(vanco_x_train, vanco_y_train)

vanco_tomek_index = vanco_under.sample_indices_
vanco_training_set = vanco_training_set.reset_index(drop=True)

vanco_tomek_set = vanco_training_set.drop(vanco_tomek_index)
vanco_tomek_set.to_csv('Z:\\Nathan\\Models\\student_risk\\outliers\\vanco_frsh_tomek_set.csv', encoding='utf-8', index=False)

#%%
# Tri-Cities undersample
trici_x_train = trici_training_set.drop(columns=['enrl_ind','emplid'])

trici_x_test = trici_testing_set[[
                        # 'acad_year',
						# 'age_group', 
						# 'age',
						'male',
						# 'race_hispanic',
						# 'race_american_indian',
						# 'race_alaska',
						# 'race_asian',
						# 'race_black',
						# 'race_native_hawaiian',
						# 'race_white',
						# 'min_week_from_term_begin_dt',
						# 'max_week_from_term_begin_dt',
						'count_week_from_term_begin_dt',
						# 'marital_status',
						'acs_mi',
						'distance',
						'pop_dens',
						'underrep_minority', 
						# 'ipeds_ethnic_group_descrshort',
						'pell_eligibility_ind',
						# 'pell_recipient_ind',
						'first_gen_flag',
						'first_gen_flag_mi', 
						# 'LSAMP_STEM_Flag',
						# 'anywhere_STEM_Flag',
						# 'honors_program_ind',
						# 'afl_greek_indicator',
						'high_school_gpa',
						'high_school_gpa_mi',
						'fall_midterm_gpa_avg',
						'fall_midterm_gpa_avg_mi',
						'fall_midterm_grade_count',
						# 'fall_midterm_S_grade_count',
						# 'fall_midterm_W_grade_count',
						# 'awe_instrument',
						# 'cdi_instrument',
						'fall_avg_difficulty',
						'fall_avg_pct_withdrawn',
						# 'fall_avg_pct_CDFW',
						'fall_avg_pct_CDF',
						# 'fall_avg_pct_DFW',
						# 'fall_avg_pct_DF',
						# 'fall_crse_mi',
						'fall_lec_count',
						'fall_lab_count',
						# 'fall_int_count',
						# 'fall_stu_count',
						# 'fall_sem_count',
						# 'fall_oth_count',
						# 'fall_lec_contact_hrs',
						# 'fall_lab_contact_hrs',
						# 'fall_int_contact_hrs',
						# 'fall_stu_contact_hrs',
						# 'fall_sem_contact_hrs',
						# 'fall_oth_contact_hrs',
						# 'total_fall_contact_hrs',
						'cum_adj_transfer_hours',
						'resident',
						# 'father_wsu_flag',
						# 'mother_wsu_flag',
						'parent1_highest_educ_lvl',
						'parent2_highest_educ_lvl',
						# 'citizenship_country',
						'gini_indx',
						'pvrt_rate',
						'median_inc',
						'median_value',
						'educ_rate',
						'pct_blk',
						'pct_ai',
						'pct_asn',
						'pct_hawi',
						'pct_oth',
						'pct_two',
						# 'pct_non',
						'pct_hisp',
						# 'city_large',
						# 'city_mid',
						# 'city_small',
						# 'suburb_large',
						# 'suburb_mid',
						# 'suburb_small',
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
						'fall_credit_hours',
						# 'total_fall_units',
						'fall_withdrawn_hours',
						# 'fall_withdrawn_ind',
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
						'unmet_need_ofr',
						'unmet_need_ofr_mi'
                        ]]

trici_y_train = trici_training_set['enrl_ind']
# trici_y_test = trici_testing_set['enrl_ind']

trici_tomek_prep = make_column_transformer(
	(StandardScaler(), [
						'distance',
						# 'age',
						# 'min_week_from_term_begin_dt',
						# 'max_week_from_term_begin_dt',
						'count_week_from_term_begin_dt',
						# 'sat_erws',
						# 'sat_mss',
						# 'sat_comp',
						# 'attendee_total_visits',
						'pop_dens', 
						# 'qvalue', 
						# 'gini_indx',
						'median_inc',
						# 'pvrt_rate',
						'median_value',
						# 'educ_rate',
						# 'pct_blk',
						# 'pct_ai',
						# 'pct_asn',
						# 'pct_hawi',
						# 'pct_oth',
						# 'pct_two',
						# 'pct_non',
						# 'pct_hisp',
						'high_school_gpa',
						'fall_midterm_gpa_avg',
						'fall_midterm_grade_count',
						# 'fall_midterm_S_grade_count',
						# 'fall_midterm_W_grade_count',
						# 'awe_instrument',
						# 'cdi_instrument',
						'fall_avg_difficulty',
						# 'fall_avg_pct_withdrawn',
						# 'fall_avg_pct_CDFW',
						# 'fall_avg_pct_CDF',
						'fall_lec_count',
						'fall_lab_count',
						# 'fall_int_count',
						# 'fall_stu_count',
						# 'fall_sem_count',
						# 'fall_oth_count',
						# 'fall_lec_contact_hrs',
						# 'fall_lab_contact_hrs',
						# 'fall_int_contact_hrs',
						# 'fall_stu_contact_hrs',
						# 'fall_sem_contact_hrs',
						# 'fall_oth_contact_hrs',
						# 'total_fall_contact_hrs',
						# 'total_fall_units',
						'fall_credit_hours',
						'fall_withdrawn_hours',
						'cum_adj_transfer_hours',
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

trici_x_train = trici_tomek_prep.fit_transform(trici_x_train)
trici_x_test = trici_tomek_prep.transform(trici_x_test)

trici_feat_names = []

for name, transformer, features, _ in trici_tomek_prep._iter(fitted=True):

	if transformer != 'passthrough':
		try:
			trici_feat_names.extend(trici_tomek_prep.named_transformers_[name].get_feature_names())
		except AttributeError:
			trici_feat_names.extend(features)

	if transformer == 'passthrough':
		trici_feat_names.extend(trici_tomek_prep._feature_names_in[features])

trici_under = TomekLinks(sampling_strategy='all', n_jobs=-1)
trici_x_train, trici_y_train = trici_under.fit_resample(trici_x_train, trici_y_train)

trici_tomek_index = trici_under.sample_indices_
trici_training_set = trici_training_set.reset_index(drop=True)

trici_tomek_set = trici_training_set.drop(trici_tomek_index)
trici_tomek_set.to_csv('Z:\\Nathan\\Models\\student_risk\\outliers\\trici_frsh_tomek_set.csv', encoding='utf-8', index=False)

#%%
# University undersample
univr_x_train = univr_training_set.drop(columns=['enrl_ind','emplid'])

univr_x_test = univr_testing_set[[
                        # 'acad_year',
						# 'age_group', 
						# 'age',
						'male',
						# 'race_hispanic',
						# 'race_american_indian',
						# 'race_alaska',
						# 'race_asian',
						# 'race_black',
						# 'race_native_hawaiian',
						# 'race_white',
						# 'min_week_from_term_begin_dt',
						# 'max_week_from_term_begin_dt',
						'count_week_from_term_begin_dt',
						# 'marital_status',
						'acs_mi',
						'distance',
						'pop_dens',
						'underrep_minority', 
						# 'ipeds_ethnic_group_descrshort',
						'pell_eligibility_ind',
						# 'pell_recipient_ind',
						'first_gen_flag',
						'first_gen_flag_mi', 
						# 'LSAMP_STEM_Flag',
						# 'anywhere_STEM_Flag',
						# 'honors_program_ind',
						# 'afl_greek_indicator',
						'high_school_gpa',
						'high_school_gpa_mi',
						'fall_midterm_gpa_avg',
						'fall_midterm_gpa_avg_mi',
						'fall_midterm_grade_count',
						'fall_midterm_S_grade_count',
						'fall_midterm_W_grade_count',
						# 'awe_instrument',
						# 'cdi_instrument',
						'fall_avg_difficulty',
						'fall_avg_pct_withdrawn',
						# 'fall_avg_pct_CDFW',
						'fall_avg_pct_CDF',
						# 'fall_avg_pct_DFW',
						# 'fall_avg_pct_DF',
						# 'fall_crse_mi',
						'fall_lec_count',
						'fall_lab_count',
						# 'fall_int_count',
						# 'fall_stu_count',
						# 'fall_sem_count',
						# 'fall_oth_count',
						# 'fall_lec_contact_hrs',
						# 'fall_lab_contact_hrs',
						# 'fall_int_contact_hrs',
						# 'fall_stu_contact_hrs',
						# 'fall_sem_contact_hrs',
						# 'fall_oth_contact_hrs',
						# 'total_fall_contact_hrs',
						'cum_adj_transfer_hours',
						'resident',
						# 'father_wsu_flag',
						# 'mother_wsu_flag',
						'parent1_highest_educ_lvl',
						'parent2_highest_educ_lvl',
						# 'citizenship_country',
						'gini_indx',
						'pvrt_rate',
						'median_inc',
						'median_value',
						'educ_rate',
						'pct_blk',
						'pct_ai',
						'pct_asn',
						'pct_hawi',
						'pct_oth',
						'pct_two',
						# 'pct_non',
						'pct_hisp',
						# 'city_large',
						# 'city_mid',
						# 'city_small',
						# 'suburb_large',
						# 'suburb_mid',
						# 'suburb_small',
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
						'fall_credit_hours',
						# 'total_fall_units',
						'fall_withdrawn_hours',
						# 'fall_withdrawn_ind',
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
						'unmet_need_ofr',
						'unmet_need_ofr_mi'
                        ]]

univr_y_train = univr_training_set['enrl_ind']
# univr_y_test = univr_testing_set['enrl_ind']

univr_tomek_prep = make_column_transformer(
	(StandardScaler(), [
						'distance',
						# 'age',
						# 'min_week_from_term_begin_dt',
						# 'max_week_from_term_begin_dt',
						'count_week_from_term_begin_dt',
						# 'sat_erws',
						# 'sat_mss',
						# 'sat_comp',
						# 'attendee_total_visits',
						'pop_dens', 
						# 'qvalue', 
						# 'gini_indx',
						'median_inc',
						# 'pvrt_rate',
						'median_value',
						# 'educ_rate',
						# 'pct_blk',
						# 'pct_ai',
						# 'pct_asn',
						# 'pct_hawi',
						# 'pct_oth',
						# 'pct_two',
						# 'pct_non',
						# 'pct_hisp',
						'high_school_gpa',
						'fall_midterm_gpa_avg',
						'fall_midterm_grade_count',
						'fall_midterm_S_grade_count',
						'fall_midterm_W_grade_count',
						# 'awe_instrument',
						# 'cdi_instrument',
						'fall_avg_difficulty',
						# 'fall_avg_pct_withdrawn',
						# 'fall_avg_pct_CDFW',
						# 'fall_avg_pct_CDF',
						'fall_lec_count',
						'fall_lab_count',
						# 'fall_int_count',
						# 'fall_stu_count',
						# 'fall_sem_count',
						# 'fall_oth_count',
						# 'fall_lec_contact_hrs',
						# 'fall_lab_contact_hrs',
						# 'fall_int_contact_hrs',
						# 'fall_stu_contact_hrs',
						# 'fall_sem_contact_hrs',
						# 'fall_oth_contact_hrs',
						# 'total_fall_contact_hrs',
						# 'total_fall_units',
						'fall_credit_hours',
						'fall_withdrawn_hours',
						'cum_adj_transfer_hours',
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

univr_x_train = univr_tomek_prep.fit_transform(univr_x_train)
univr_x_test = univr_tomek_prep.transform(univr_x_test)

univr_feat_names = []

for name, transformer, features, _ in univr_tomek_prep._iter(fitted=True):

	if transformer != 'passthrough':
		try:
			univr_feat_names.extend(univr_tomek_prep.named_transformers_[name].get_feature_names())
		except AttributeError:
			univr_feat_names.extend(features)

	if transformer == 'passthrough':
		univr_feat_names.extend(univr_tomek_prep._feature_names_in[features])

univr_under = TomekLinks(sampling_strategy='all', n_jobs=-1)
univr_x_train, univr_y_train = univr_under.fit_resample(univr_x_train, univr_y_train)

univr_tomek_index = univr_under.sample_indices_
univr_training_set = univr_training_set.reset_index(drop=True)

univr_tomek_set = univr_training_set.drop(univr_tomek_index)
univr_tomek_set.to_csv('Z:\\Nathan\\Models\\student_risk\\outliers\\univr_frsh_tomek_set.csv', encoding='utf-8', index=False)

#%%
# Standard logistic model

# Pullman standard model
print('\nStandard logistic model for Pullman freshmen...\n')

pullm_y, pullm_x = dmatrices('enrl_ind ~ distance + pvrt_rate + pop_dens + educ_rate \
				+ pct_blk + pct_ai + pct_asn + pct_hawi + pct_two + pct_hisp + pct_oth \
				+ gini_indx + median_inc + median_value + acs_mi \
				+ male + underrep_minority + pell_eligibility_ind + first_gen_flag + first_gen_flag_mi \
                + fall_avg_difficulty + fall_avg_pct_CDF + fall_avg_pct_withdrawn \
				+ fall_lec_count + fall_lab_count + fall_stu_count + fall_oth_count \
				+ fall_credit_hours \
				+ fall_withdrawn_hours \
                + honors_program_ind \
				+ AD_DTA + AD_AST + AP + RS + CHS + IB_AICE \
				+ business + comm + education + medicine + nursing + vet_med \
				+ cahnrs_anml + cahnrs_econ + cahnrext \
				+ cas_chem + cas_crim + cas_math + cas_psyc + cas_biol + cas_engl + cas_phys + cas \
                + vcea_bioe + vcea_cive + vcea_desn + vcea_eecs + vcea_mech + vcea \
				+ remedial \
				+ cum_adj_transfer_hours \
				+ resident \
            	+ high_school_gpa + high_school_gpa_mi \
				+ fall_midterm_gpa_avg + fall_midterm_gpa_avg_mi \
				+ fall_midterm_grade_count + fall_midterm_S_grade_count + fall_midterm_W_grade_count \
				+ parent1_highest_educ_lvl + parent2_highest_educ_lvl \
            	+ unmet_need_ofr + unmet_need_ofr_mi \
				+ count_week_from_term_begin_dt', data=pullm_logit_df, return_type='dataframe')

pullm_logit_mod = Logit(pullm_y, pullm_x)
pullm_logit_res = pullm_logit_mod.fit(maxiter=500)
print(pullm_logit_res.summary())

print('\n')

#%%
# Vancouver standard model
print('\nStandard logistic model for Vancouver freshmen...\n')

vanco_y, vanco_x = dmatrices('enrl_ind ~ distance + pvrt_rate + pop_dens + educ_rate \
				+ pct_blk + pct_ai + pct_asn + pct_hawi + pct_two + pct_hisp + pct_oth \
				+ gini_indx + median_inc + median_value + acs_mi \
				+ male + underrep_minority + pell_eligibility_ind + first_gen_flag + first_gen_flag_mi \
                + fall_avg_difficulty + fall_avg_pct_CDF + fall_avg_pct_withdrawn \
				+ fall_lec_count + fall_lab_count \
				+ fall_credit_hours \
				+ fall_withdrawn_hours \
				+ remedial \
				+ cum_adj_transfer_hours \
				+ resident \
            	+ high_school_gpa + high_school_gpa_mi \
				+ fall_midterm_gpa_avg + fall_midterm_gpa_avg_mi \
				+ fall_midterm_grade_count \
				+ parent1_highest_educ_lvl + parent2_highest_educ_lvl \
            	+ unmet_need_ofr + unmet_need_ofr_mi \
				+ count_week_from_term_begin_dt', data=vanco_logit_df, return_type='dataframe')

vanco_logit_mod = Logit(vanco_y, vanco_x)
vanco_logit_res = vanco_logit_mod.fit(maxiter=500)
print(vanco_logit_res.summary())

print('\n')

#%%
# Tri-Cities standard model
print('\nStandard logistic model for Tri-Cities freshmen...\n')

trici_y, trici_x = dmatrices('enrl_ind ~ distance + pvrt_rate + pop_dens + educ_rate \
				+ pct_blk + pct_ai + pct_asn + pct_hawi + pct_two + pct_hisp + pct_oth \
				+ gini_indx + median_inc + median_value + acs_mi \
				+ male + underrep_minority + pell_eligibility_ind + first_gen_flag + first_gen_flag_mi \
                + fall_avg_difficulty + fall_avg_pct_CDF + fall_avg_pct_withdrawn \
				+ fall_lec_count + fall_lab_count \
				+ fall_credit_hours \
				+ fall_withdrawn_hours \
				+ remedial \
				+ cum_adj_transfer_hours \
				+ resident \
            	+ high_school_gpa + high_school_gpa_mi \
				+ fall_midterm_gpa_avg + fall_midterm_gpa_avg_mi \
				+ fall_midterm_grade_count \
				+ parent1_highest_educ_lvl + parent2_highest_educ_lvl \
            	+ unmet_need_ofr + unmet_need_ofr_mi \
				+ count_week_from_term_begin_dt', data=trici_logit_df, return_type='dataframe')

trici_logit_mod = Logit(trici_y, trici_x)
trici_logit_res = trici_logit_mod.fit(maxiter=500)
print(trici_logit_res.summary())

print('\n')

#%%
# University standard model
print('\nStandard logistic model for University freshmen...\n')

univr_y, univr_x = dmatrices('enrl_ind ~ distance + pvrt_rate + pop_dens + educ_rate \
				+ pct_blk + pct_ai + pct_asn + pct_hawi + pct_two + pct_hisp + pct_oth \
				+ gini_indx + median_inc + median_value + acs_mi \
				+ male + underrep_minority + pell_eligibility_ind + first_gen_flag + first_gen_flag_mi \
                + fall_avg_difficulty + fall_avg_pct_CDF + fall_avg_pct_withdrawn \
				+ fall_lec_count + fall_lab_count \
				+ fall_credit_hours \
				+ fall_withdrawn_hours \
				+ remedial \
				+ cum_adj_transfer_hours \
				+ resident \
            	+ high_school_gpa + high_school_gpa_mi \
				+ fall_midterm_gpa_avg + fall_midterm_gpa_avg_mi \
				+ fall_midterm_grade_count + fall_midterm_S_grade_count + fall_midterm_W_grade_count \
				+ parent1_highest_educ_lvl + parent2_highest_educ_lvl \
            	+ unmet_need_ofr + unmet_need_ofr_mi \
				+ count_week_from_term_begin_dt', data=univr_logit_df, return_type='dataframe')

univr_logit_mod = Logit(univr_y, univr_x)
univr_logit_res = univr_logit_mod.fit(maxiter=500)
print(univr_logit_res.summary())

print('\n')

#%%
# VIF diagnostic

# Pullman VIF
print('VIF for Pullman...\n')
pullm_vif = pd.DataFrame()
pullm_vif['vif factor'] = [variance_inflation_factor(pullm_x.values, i) for i in range(pullm_x.shape[1])]
pullm_vif['features'] = pullm_x.columns
pullm_vif.sort_values(by=['vif factor'], ascending=False, inplace=True, ignore_index=True)
print(pullm_vif.round(1).to_string())
print('\n')

#%%
# Vancouver VIF
print('VIF for Vancouver...\n')
vanco_vif = pd.DataFrame()
vanco_vif['vif factor'] = [variance_inflation_factor(vanco_x.values, i) for i in range(vanco_x.shape[1])]
vanco_vif['features'] = vanco_x.columns
vanco_vif.sort_values(by=['vif factor'], ascending=False, inplace=True, ignore_index=True)
print(vanco_vif.round(1).to_string())
print('\n')

#%%
# Tri-Cities VIF
print('VIF for Tri-Cities...\n')
trici_vif = pd.DataFrame()
trici_vif['vif factor'] = [variance_inflation_factor(trici_x.values, i) for i in range(trici_x.shape[1])]
trici_vif['features'] = trici_x.columns
trici_vif.sort_values(by=['vif factor'], ascending=False, inplace=True, ignore_index=True)
print(trici_vif.round(1).to_string())
print('\n')

#%%
# University VIF
print('VIF for University...\n')
univr_vif = pd.DataFrame()
univr_vif['vif factor'] = [variance_inflation_factor(univr_x.values, i) for i in range(univr_x.shape[1])]
univr_vif['features'] = univr_x.columns
univr_vif.sort_values(by=['vif factor'], ascending=False, inplace=True, ignore_index=True)
print(univr_vif.round(1).to_string())
print('\n')

#%%
print('Run machine learning models for freshmen...\n')

# Logistic model

# Pullman logistic
pullm_lreg = LogisticRegression(penalty='elasticnet', class_weight='balanced', solver='saga', max_iter=5000, l1_ratio=0.0, C=1.0, n_jobs=-1, verbose=False).fit(pullm_x_train, pullm_y_train)

pullm_lreg_probs = pullm_lreg.predict_proba(pullm_x_train)
pullm_lreg_probs = pullm_lreg_probs[:, 1]
pullm_lreg_auc = roc_auc_score(pullm_y_train, pullm_lreg_probs)

print(f'\nOverall accuracy for Pullman logistic model (training): {pullm_lreg.score(pullm_x_train, pullm_y_train):.4f}')
print(f'ROC AUC for Pullman logistic model (training): {pullm_lreg_auc:.4f}\n')

pullm_lreg_fpr, pullm_lreg_tpr, pullm_thresholds = roc_curve(pullm_y_train, pullm_lreg_probs, drop_intermediate=False)

#%%
# Vancouver logistic
vanco_lreg = LogisticRegression(penalty='elasticnet', class_weight='balanced', solver='saga', max_iter=5000, l1_ratio=0.0, C=1.0, n_jobs=-1, verbose=False).fit(vanco_x_train, vanco_y_train)

vanco_lreg_probs = vanco_lreg.predict_proba(vanco_x_train)
vanco_lreg_probs = vanco_lreg_probs[:, 1]
vanco_lreg_auc = roc_auc_score(vanco_y_train, vanco_lreg_probs)

print(f'\nOverall accuracy for Vancouver logistic model (training): {vanco_lreg.score(vanco_x_train, vanco_y_train):.4f}')
print(f'ROC AUC for Vancouver logistic model (training): {vanco_lreg_auc:.4f}\n')

vanco_lreg_fpr, vanco_lreg_tpr, vanco_thresholds = roc_curve(vanco_y_train, vanco_lreg_probs, drop_intermediate=False)

#%%
# Tri-Cities logistic
trici_lreg = LogisticRegression(penalty='elasticnet', class_weight='balanced', solver='saga', max_iter=5000, l1_ratio=0.0, C=1.0, n_jobs=-1, verbose=False).fit(trici_x_train, trici_y_train)

trici_lreg_probs = trici_lreg.predict_proba(trici_x_train)
trici_lreg_probs = trici_lreg_probs[:, 1]
trici_lreg_auc = roc_auc_score(trici_y_train, trici_lreg_probs)

print(f'\nOverall accuracy for Tri-Cities logistic model (training): {trici_lreg.score(trici_x_train, trici_y_train):.4f}')
print(f'ROC AUC for Tri-Cities logistic model (training): {trici_lreg_auc:.4f}\n')

trici_lreg_fpr, trici_lreg_tpr, trici_thresholds = roc_curve(trici_y_train, trici_lreg_probs, drop_intermediate=False)

#%%
# University logistic
univr_lreg = LogisticRegression(penalty='elasticnet', class_weight='balanced', solver='saga', max_iter=5000, l1_ratio=0.0, C=1.0, n_jobs=-1, verbose=False).fit(univr_x_train, univr_y_train)

univr_lreg_probs = univr_lreg.predict_proba(univr_x_train)
univr_lreg_probs = univr_lreg_probs[:, 1]
univr_lreg_auc = roc_auc_score(univr_y_train, univr_lreg_probs)

print(f'\nOverall accuracy for University logistic model (training): {univr_lreg.score(univr_x_train, univr_y_train):.4f}')
print(f'ROC AUC for University logistic model (training): {univr_lreg_auc:.4f}\n')

univr_lreg_fpr, univr_lreg_tpr, univr_thresholds = roc_curve(univr_y_train, univr_lreg_probs, drop_intermediate=False)

#%%
# Stochastic gradient descent model

# Pullman SGD
pullm_sgd = SGDClassifier(loss='modified_huber', penalty='elasticnet', class_weight='balanced', early_stopping=False, max_iter=5000, l1_ratio=0.0, learning_rate='adaptive', eta0=0.0001, tol=0.0001, n_iter_no_change=100, n_jobs=-1, verbose=False).fit(pullm_x_train, pullm_y_train)

pullm_sgd_probs = pullm_sgd.predict_proba(pullm_x_train)
pullm_sgd_probs = pullm_sgd_probs[:, 1]
pullm_sgd_auc = roc_auc_score(pullm_y_train, pullm_sgd_probs)

print(f'\nOverall accuracy for Pullman SGD model (training): {pullm_sgd.score(pullm_x_train, pullm_y_train):.4f}')
print(f'ROC AUC for Pullman SGD model (training): {pullm_sgd_auc:.4f}\n')

pullm_sgd_fpr, pullm_sgd_tpr, pullm_thresholds = roc_curve(pullm_y_train, pullm_sgd_probs, drop_intermediate=False)

#%%
# Vancouver SGD
vanco_sgd = SGDClassifier(loss='modified_huber', penalty='elasticnet', class_weight='balanced', early_stopping=False, max_iter=5000, l1_ratio=0.0, learning_rate='adaptive', eta0=0.0001, tol=0.0001, n_iter_no_change=100, n_jobs=-1, verbose=False).fit(vanco_x_train, vanco_y_train)

vanco_sgd_probs = vanco_sgd.predict_proba(vanco_x_train)
vanco_sgd_probs = vanco_sgd_probs[:, 1]
vanco_sgd_auc = roc_auc_score(vanco_y_train, vanco_sgd_probs)

print(f'\nOverall accuracy for Vancouver SGD model (training): {vanco_sgd.score(vanco_x_train, vanco_y_train):.4f}')
print(f'ROC AUC for Vancouver SGD model (training): {vanco_sgd_auc:.4f}\n')

vanco_sgd_fpr, vanco_sgd_tpr, vanco_thresholds = roc_curve(vanco_y_train, vanco_sgd_probs, drop_intermediate=False)

#%%
# Tri-Cities SGD
trici_sgd = SGDClassifier(loss='modified_huber', penalty='elasticnet', class_weight='balanced', early_stopping=False, max_iter=5000, l1_ratio=0.0, learning_rate='adaptive', eta0=0.0001, tol=0.0001, n_iter_no_change=100, n_jobs=-1, verbose=False).fit(trici_x_train, trici_y_train)

trici_sgd_probs = trici_sgd.predict_proba(trici_x_train)
trici_sgd_probs = trici_sgd_probs[:, 1]
trici_sgd_auc = roc_auc_score(trici_y_train, trici_sgd_probs)

print(f'\nOverall accuracy for Tri-Cities SGD model (training): {trici_sgd.score(trici_x_train, trici_y_train):.4f}')
print(f'ROC AUC for Tri-Cities SGD model (training): {trici_sgd_auc:.4f}\n')

trici_sgd_fpr, trici_sgd_tpr, trici_thresholds = roc_curve(trici_y_train, trici_sgd_probs, drop_intermediate=False)

#%%
# University SGD
univr_sgd = SGDClassifier(loss='modified_huber', penalty='elasticnet', class_weight='balanced', early_stopping=False, max_iter=5000, l1_ratio=0.0, learning_rate='adaptive', eta0=0.0001, tol=0.0001, n_iter_no_change=100, n_jobs=-1, verbose=False).fit(univr_x_train, univr_y_train)

univr_sgd_probs = univr_sgd.predict_proba(univr_x_train)
univr_sgd_probs = univr_sgd_probs[:, 1]
univr_sgd_auc = roc_auc_score(univr_y_train, univr_sgd_probs)

print(f'\nOverall accuracy for University SGD model (training): {univr_sgd.score(univr_x_train, univr_y_train):.4f}')
print(f'ROC AUC for University SGD model (training): {univr_sgd_auc:.4f}\n')

univr_sgd_fpr, univr_sgd_tpr, univr_thresholds = roc_curve(univr_y_train, univr_sgd_probs, drop_intermediate=False)

#%%
# XGBoost model

# Pullman XGB
class_weight = pullm_y_train[pullm_y_train == 0].count() / pullm_y_train[pullm_y_train == 1].count()
pullm_xgb = XGBClassifier(scale_pos_weight=class_weight, eval_metric='logloss', use_label_encoder=False).fit(pullm_x_train, pullm_y_train)

pullm_xgb_probs = pullm_xgb.predict_proba(pullm_x_train)
pullm_xgb_probs = pullm_xgb_probs[:, 1]
pullm_xgb_auc = roc_auc_score(pullm_y_train, pullm_xgb_probs)

print(f'\nOverall accuracy for Pullman XGB model (training): {pullm_xgb.score(pullm_x_train, pullm_y_train):.4f}')
print(f'ROC AUC for Pullman XGB model (training): {pullm_xgb_auc:.4f}\n')

pullm_xgb_fpr, pullm_xgb_tpr, pullm_thresholds = roc_curve(pullm_y_train, pullm_xgb_probs, drop_intermediate=False)

#%%
# Vancouver XGB
class_weight = vanco_y_train[vanco_y_train == 0].count() / vanco_y_train[vanco_y_train == 1].count()
vanco_xgb = XGBClassifier(scale_pos_weight=class_weight, eval_metric='logloss', use_label_encoder=False).fit(vanco_x_train, vanco_y_train)

vanco_xgb_probs = vanco_xgb.predict_proba(vanco_x_train)
vanco_xgb_probs = vanco_xgb_probs[:, 1]
vanco_xgb_auc = roc_auc_score(vanco_y_train, vanco_xgb_probs)

print(f'\nOverall accuracy for Vancouver XGB model (training): {vanco_xgb.score(vanco_x_train, vanco_y_train):.4f}')
print(f'ROC AUC for Vancouver XGB model (training): {vanco_xgb_auc:.4f}\n')

vanco_xgb_fpr, vanco_xgb_tpr, vanco_thresholds = roc_curve(vanco_y_train, vanco_xgb_probs, drop_intermediate=False)

#%%
# Tri-Cities XGB
class_weight = trici_y_train[trici_y_train == 0].count() / trici_y_train[trici_y_train == 1].count()
trici_xgb = XGBClassifier(scale_pos_weight=class_weight, eval_metric='logloss', use_label_encoder=False).fit(trici_x_train, trici_y_train)

trici_xgb_probs = trici_xgb.predict_proba(trici_x_train)
trici_xgb_probs = trici_xgb_probs[:, 1]
trici_xgb_auc = roc_auc_score(trici_y_train, trici_xgb_probs)

print(f'\nOverall accuracy for Tri-Cities XGB model (training): {trici_xgb.score(trici_x_train, trici_y_train):.4f}')
print(f'ROC AUC for Tri-Cities XGB model (training): {trici_xgb_auc:.4f}\n')

trici_xgb_fpr, trici_xgb_tpr, trici_thresholds = roc_curve(trici_y_train, trici_xgb_probs, drop_intermediate=False)

#%%
# University XGB
class_weight = univr_y_train[univr_y_train == 0].count() / univr_y_train[univr_y_train == 1].count()
univr_xgb = XGBClassifier(scale_pos_weight=class_weight, eval_metric='logloss', use_label_encoder=False).fit(univr_x_train, univr_y_train)

univr_xgb_probs = univr_xgb.predict_proba(univr_x_train)
univr_xgb_probs = univr_xgb_probs[:, 1]
univr_xgb_auc = roc_auc_score(univr_y_train, univr_xgb_probs)

print(f'\nOverall accuracy for University XGB model (training): {univr_xgb.score(univr_x_train, univr_y_train):.4f}')
print(f'ROC AUC for University XGB model (training): {univr_xgb_auc:.4f}\n')

univr_xgb_fpr, univr_xgb_tpr, univr_thresholds = roc_curve(univr_y_train, univr_xgb_probs, drop_intermediate=False)

#%%
# Multi-layer perceptron model

# Pullman MLP
# pullm_mlp = MLPClassifier(hidden_layer_sizes=(75,50,25), activation='relu', solver='sgd', alpha=2.5, learning_rate_init=0.001, n_iter_no_change=25, max_iter=5000, verbose=False).fit(pullm_x_train, pullm_y_train)

# pullm_mlp_probs = pullm_mlp.predict_proba(pullm_x_train)
# pullm_mlp_probs = pullm_mlp_probs[:, 1]
# pullm_mlp_auc = roc_auc_score(pullm_y_train, pullm_mlp_probs)

# print(f'\nOverall accuracy for multi-layer perceptron model (training): {pullm_mlp.score(pullm_x_train, pullm_y_train):.4f}')
# print(f'ROC AUC for multi-layer perceptron model (training): {pullm_mlp_auc:.4f}\n')

# mlp_fpr, mlp_tpr, thresholds = roc_curve(pullm_y_train, pullm_mlp_probs, drop_intermediate=False)

#%%
# Vancouver MLP
# vanco_mlp = MLPClassifier(hidden_layer_sizes=(75,50,25), activation='relu', solver='sgd', alpha=2.5, learning_rate_init=0.001, n_iter_no_change=25, max_iter=5000, verbose=False).fit(vanco_x_train, vanco_y_train)

# vanco_mlp_probs = vanco_mlp.predict_proba(vanco_x_train)
# vanco_mlp_probs = vanco_mlp_probs[:, 1]
# vanco_mlp_auc = roc_auc_score(vanco_y_train, vanco_mlp_probs)

# print(f'\nOverall accuracy for multi-layer perceptron model (training): {vanco_mlp.score(vanco_x_train, vanco_y_train):.4f}')
# print(f'ROC AUC for multi-layer perceptron model (training): {vanco_mlp_auc:.4f}\n')

# mlp_fpr, mlp_tpr, thresholds = roc_curve(vanco_y_train, vanco_mlp_probs, drop_intermediate=False)

#%%
# Tri-Cities MLP
# trici_mlp = MLPClassifier(hidden_layer_sizes=(75,50,25), activation='relu', solver='sgd', alpha=2.5, learning_rate_init=0.001, n_iter_no_change=25, max_iter=5000, verbose=False).fit(trici_x_train, trici_y_train)

# trici_mlp_probs = trici_mlp.predict_proba(trici_x_train)
# trici_mlp_probs = trici_mlp_probs[:, 1]
# trici_mlp_auc = roc_auc_score(trici_y_train, trici_mlp_probs)

# print(f'\nOverall accuracy for multi-layer perceptron model (training): {trici_mlp.score(trici_x_train, trici_y_train):.4f}')
# print(f'ROC AUC for multi-layer perceptron model (training): {trici_mlp_auc:.4f}\n')

# mlp_fpr, mlp_tpr, thresholds = roc_curve(trici_y_train, trici_mlp_probs, drop_intermediate=False)

#%%
# University MLP
# univr_mlp = MLPClassifier(hidden_layer_sizes=(75,50,25), activation='relu', solver='sgd', alpha=2.5, learning_rate_init=0.001, n_iter_no_change=25, max_iter=5000, verbose=False).fit(univr_x_train, univr_y_train)

# univr_mlp_probs = univr_mlp.predict_proba(univr_x_train)
# univr_mlp_probs = univr_mlp_probs[:, 1]
# univr_mlp_auc = roc_auc_score(univr_y_train, univr_mlp_probs)

# print(f'\nOverall accuracy for University multi-layer perceptron model (training): {univr_mlp.score(univr_x_train, univr_y_train):.4f}')
# print(f'ROC AUC for University multi-layer perceptron model (training): {univr_mlp_auc:.4f}\n')

# mlp_fpr, mlp_tpr, thresholds = roc_curve(univr_y_train, univr_mlp_probs, drop_intermediate=False)

#%%
# Ensemble model

# Pullman VCF
pullm_vcf = VotingClassifier(estimators=[('lreg', pullm_lreg), ('sgd', pullm_sgd)], voting='soft', weights=[1, 1]).fit(pullm_x_train, pullm_y_train)

pullm_vcf_probs = pullm_vcf.predict_proba(pullm_x_train)
pullm_vcf_probs = pullm_vcf_probs[:, 1]
pullm_vcf_auc = roc_auc_score(pullm_y_train, pullm_vcf_probs)

print(f'\nOverall accuracy for Pullman ensemble model (training): {pullm_vcf.score(pullm_x_train, pullm_y_train):.4f}')
print(f'ROC AUC for Pullman ensemble model (training): {pullm_vcf_auc:.4f}\n')

pullm_vcf_fpr, pullm_vcf_tpr, pullm_thresholds = roc_curve(pullm_y_train, pullm_vcf_probs, drop_intermediate=False)

#%%
# Vancouver VCF
vanco_vcf = VotingClassifier(estimators=[('lreg', vanco_lreg), ('sgd', vanco_sgd)], voting='soft', weights=[1, 1]).fit(vanco_x_train, vanco_y_train)

vanco_vcf_probs = vanco_vcf.predict_proba(vanco_x_train)
vanco_vcf_probs = vanco_vcf_probs[:, 1]
vanco_vcf_auc = roc_auc_score(vanco_y_train, vanco_vcf_probs)

print(f'\nOverall accuracy for Vancouver ensemble model (training): {vanco_vcf.score(vanco_x_train, vanco_y_train):.4f}')
print(f'ROC AUC for Vancouver ensemble model (training): {vanco_vcf_auc:.4f}\n')

vanco_vcf_fpr, vanco_vcf_tpr, vanco_thresholds = roc_curve(vanco_y_train, vanco_vcf_probs, drop_intermediate=False)

#%%
# Tri-Cities VCF
trici_vcf = VotingClassifier(estimators=[('lreg', trici_lreg), ('sgd', trici_sgd)], voting='soft', weights=[1, 1]).fit(trici_x_train, trici_y_train)

trici_vcf_probs = trici_vcf.predict_proba(trici_x_train)
trici_vcf_probs = trici_vcf_probs[:, 1]
trici_vcf_auc = roc_auc_score(trici_y_train, trici_vcf_probs)

print(f'\nOverall accuracy for Tri-Cities ensemble model (training): {trici_vcf.score(trici_x_train, trici_y_train):.4f}')
print(f'ROC AUC for Tri-Cities ensemble model (training): {trici_vcf_auc:.4f}\n')

trici_vcf_fpr, trici_vcf_tpr, trici_thresholds = roc_curve(trici_y_train, trici_vcf_probs, drop_intermediate=False)

#%%
# University VCF
univr_vcf = VotingClassifier(estimators=[('lreg', univr_lreg), ('sgd', univr_sgd)], voting='soft', weights=[1, 1]).fit(univr_x_train, univr_y_train)

univr_vcf_probs = univr_vcf.predict_proba(univr_x_train)
univr_vcf_probs = univr_vcf_probs[:, 1]
univr_vcf_auc = roc_auc_score(univr_y_train, univr_vcf_probs)

print(f'\nOverall accuracy for University ensemble model (training): {univr_vcf.score(univr_x_train, univr_y_train):.4f}')
print(f'ROC AUC for University ensemble model (training): {univr_vcf_auc:.4f}\n')

univr_vcf_fpr, univr_vcf_tpr, univr_thresholds = roc_curve(univr_y_train, univr_vcf_probs, drop_intermediate=False)

#%%
if datetime.datetime.today().weekday() == day_of_week:

	print('Calculate SHAP values...')

#%%
# Pullman SHAP undersample
	pullm_under_shap = NearMiss(sampling_strategy={0:(pullm_y_train[pullm_y_train == 0].count()//5), 1:(pullm_y_train[pullm_y_train == 1].count()//5)}, version=3, n_jobs=-1)
	pullm_x_shap, pullm_y_shap = pullm_under_shap.fit_resample(pullm_x_train, pullm_y_train)

#%%
# Pullman SHAP training (see: https://github.com/slundberg/shap)
	pullm_explainer = shap.KernelExplainer(model=pullm_vcf.predict_proba, data=pullm_x_shap)

#%%
# Pullman SHAP prediction
	pullm_shap_values = pullm_explainer.shap_values(X=pullm_x_test, nsamples=(pullm_y_train[pullm_y_train == 1].count()//5))

#%%
# Pullman SHAP plots
# 	for index in range(len(pullm_shap_values[0])):
# 		shap.plots._waterfall.waterfall_legacy(pullm_explainer.expected_value[0], pullm_shap_values[0][index], pullm_x_test[index], feature_names=pullm_feat_names, max_display=4)

#%%
	pullm_shap_results = []

	for index in range(len(pullm_shap_values[0])):
		pullm_shap_results.extend(pd.DataFrame(data=pullm_shap_values[0][index].reshape(1, len(pullm_feat_names)), columns=pullm_feat_names).sort_values(by=0, axis=1, key=abs, ascending=False).to_dict(orient='records'))

	pullm_shap_zip = dict(zip(pullm_shap_outcome, pullm_shap_results))

#%%
# Vancouver SHAP undersample
	vanco_under_shap = NearMiss(sampling_strategy={0:(vanco_y_train[vanco_y_train == 0].count()//2), 1:(vanco_y_train[vanco_y_train == 1].count()//2)}, version=3, n_jobs=-1)
	vanco_x_shap, vanco_y_shap = vanco_under_shap.fit_resample(vanco_x_train, vanco_y_train)

#%%
# Vancouver SHAP training (see: https://github.com/slundberg/shap)
	vanco_explainer = shap.KernelExplainer(model=vanco_vcf.predict_proba, data=vanco_x_shap)

#%%
# Vancouver SHAP prediction
	vanco_shap_values = vanco_explainer.shap_values(X=vanco_x_test, nsamples=(vanco_y_train[vanco_y_train == 1].count()//2))

#%%
# Vancouver SHAP plots
# 	for index in range(len(vanco_shap_values[0])):
# 		shap.plots._waterfall.waterfall_legacy(vanco_explainer.expected_value[0], vanco_shap_values[0][index], vanco_x_test[index], feature_names=vanco_feat_names, max_display=4)

#%%
	vanco_shap_results = []

	for index in range(len(vanco_shap_values[0])):
		vanco_shap_results.extend(pd.DataFrame(data=vanco_shap_values[0][index].reshape(1, len(vanco_feat_names)), columns=vanco_feat_names).sort_values(by=0, axis=1, key=abs, ascending=False).to_dict(orient='records'))

	vanco_shap_zip = dict(zip(vanco_shap_outcome, vanco_shap_results))

#%%
# Tri-Cities SHAP undersample
	trici_under_shap = NearMiss(sampling_strategy={0:(trici_y_train[trici_y_train == 0].count()//2), 1:(trici_y_train[trici_y_train == 1].count()//2)}, version=3, n_jobs=-1)
	trici_x_shap, trici_y_shap = trici_under_shap.fit_resample(trici_x_train, trici_y_train)

#%%
# Tri-Cities SHAP training (see: https://github.com/slundberg/shap)
	trici_explainer = shap.KernelExplainer(model=trici_vcf.predict_proba, data=trici_x_shap)

#%%
# Tri-Cities SHAP prediction
	trici_shap_values = trici_explainer.shap_values(X=trici_x_test, nsamples=(trici_y_train[trici_y_train == 1].count()//2))

#%%
# Tri-Cities SHAP plots
# 	for index in range(len(trici_shap_values[0])):
# 		shap.plots._waterfall.waterfall_legacy(trici_explainer.expected_value[0], trici_shap_values[0][index], trici_x_test[index], feature_names=trici_feat_names, max_display=4)

#%%
	trici_shap_results = []

	for index in range(len(trici_shap_values[0])):
		trici_shap_results.extend(pd.DataFrame(data=trici_shap_values[0][index].reshape(1, len(trici_feat_names)), columns=trici_feat_names).sort_values(by=0, axis=1, key=abs, ascending=False).to_dict(orient='records'))

	trici_shap_zip = dict(zip(trici_shap_outcome, trici_shap_results))

#%%
# University SHAP undersample
	univr_under_shap = NearMiss(sampling_strategy={0:(univr_y_train[univr_y_train == 0].count()//2), 1:(univr_y_train[univr_y_train == 1].count()//2)}, version=3, n_jobs=-1)
	univr_x_shap, univr_y_shap = univr_under_shap.fit_resample(univr_x_train, univr_y_train)

#%%
# University SHAP training (see: https://github.com/slundberg/shap)
	univr_explainer = shap.KernelExplainer(model=univr_vcf.predict_proba, data=univr_x_shap)

#%%
# University SHAP prediction
	univr_shap_values = univr_explainer.shap_values(X=univr_x_test, nsamples=(univr_y_train[univr_y_train == 1].count()//2))

#%%
# University SHAP plots
# 	for index in range(len(univr_shap_values[0])):
# 		shap.plots._waterfall.waterfall_legacy(univr_explainer.expected_value[0], univr_shap_values[0][index], univr_x_test[index], feature_names=univr_feat_names, max_display=4)

#%%
	univr_shap_results = []

	for index in range(len(univr_shap_values[0])):
		univr_shap_results.extend(pd.DataFrame(data=univr_shap_values[0][index].reshape(1, len(univr_feat_names)), columns=univr_feat_names).sort_values(by=0, axis=1, key=abs, ascending=False).to_dict(orient='records'))

	univr_shap_zip = dict(zip(univr_shap_outcome, univr_shap_results))

	print('Done\n')

#%%
# Prepare model predictions
print('Prepare model predictions...')

# Pullman probabilites
pullm_lreg_pred_probs = pullm_lreg.predict_proba(pullm_x_test)
pullm_lreg_pred_probs = pullm_lreg_pred_probs[:, 1]
pullm_sgd_pred_probs = pullm_sgd.predict_proba(pullm_x_test)
pullm_sgd_pred_probs = pullm_sgd_pred_probs[:, 1]
pullm_xgb_pred_probs = pullm_xgb.predict_proba(pullm_x_test)
pullm_xgb_pred_probs = pullm_xgb_pred_probs[:, 1]
# pullm_mlp_pred_probs = pullm_mlp.predict_proba(pullm_x_test)
# pullm_mlp_pred_probs = pullm_mlp_pred_probs[:, 1]
pullm_vcf_pred_probs = pullm_vcf.predict_proba(pullm_x_test)
pullm_vcf_pred_probs = pullm_vcf_pred_probs[:, 1]

#%%
# Vancouver probabilites
vanco_lreg_pred_probs = vanco_lreg.predict_proba(vanco_x_test)
vanco_lreg_pred_probs = vanco_lreg_pred_probs[:, 1]
vanco_sgd_pred_probs = vanco_sgd.predict_proba(vanco_x_test)
vanco_sgd_pred_probs = vanco_sgd_pred_probs[:, 1]
vanco_xgb_pred_probs = vanco_xgb.predict_proba(vanco_x_test)
vanco_xgb_pred_probs = vanco_xgb_pred_probs[:, 1]
# vanco_mlp_pred_probs = vanco_mlp.predict_proba(vanco_x_test)
# vanco_mlp_pred_probs = vanco_mlp_pred_probs[:, 1]
vanco_vcf_pred_probs = vanco_vcf.predict_proba(vanco_x_test)
vanco_vcf_pred_probs = vanco_vcf_pred_probs[:, 1]

#%%
# Tri-Cities probabilities
trici_lreg_pred_probs = trici_lreg.predict_proba(trici_x_test)
trici_lreg_pred_probs = trici_lreg_pred_probs[:, 1]
trici_sgd_pred_probs = trici_sgd.predict_proba(trici_x_test)
trici_sgd_pred_probs = trici_sgd_pred_probs[:, 1]
trici_xgb_pred_probs = trici_xgb.predict_proba(trici_x_test)
trici_xgb_pred_probs = trici_xgb_pred_probs[:, 1]
# trici_mlp_pred_probs = trici_mlp.predict_proba(trici_x_test)
# trici_mlp_pred_probs = trici_mlp_pred_probs[:, 1]
trici_vcf_pred_probs = trici_vcf.predict_proba(trici_x_test)
trici_vcf_pred_probs = trici_vcf_pred_probs[:, 1]

#%%
# University probabilities
univr_lreg_pred_probs = univr_lreg.predict_proba(univr_x_test)
univr_lreg_pred_probs = univr_lreg_pred_probs[:, 1]
univr_sgd_pred_probs = univr_sgd.predict_proba(univr_x_test)
univr_sgd_pred_probs = univr_sgd_pred_probs[:, 1]
univr_xgb_pred_probs = univr_xgb.predict_proba(univr_x_test)
univr_xgb_pred_probs = univr_xgb_pred_probs[:, 1]
# univr_mlp_pred_probs = univr_mlp.predict_proba(univr_x_test)
# univr_mlp_pred_probs = univr_mlp_pred_probs[:, 1]
univr_vcf_pred_probs = univr_vcf.predict_proba(univr_x_test)
univr_vcf_pred_probs = univr_vcf_pred_probs[:, 1]

print('Done\n')

#%%
# Output model predictions to file
print('Output model predictions and model...')

# Pullman predicted outcome
pullm_pred_outcome['lr_prob'] = pd.DataFrame(pullm_lreg_pred_probs)
pullm_pred_outcome['lr_pred'] = pullm_lreg.predict(pullm_x_test)
pullm_pred_outcome['sgd_prob'] = pd.DataFrame(pullm_sgd_pred_probs)
pullm_pred_outcome['sgd_pred'] = pullm_sgd.predict(pullm_x_test)
pullm_pred_outcome['xgb_prob'] = pd.DataFrame(pullm_xgb_pred_probs)
pullm_pred_outcome['xgb_pred'] = pullm_xgb.predict(pullm_x_test)
# pullm_pred_outcome['mlp_prob'] = pd.DataFrame(pullm_mlp_pred_probs)
# pullm_pred_outcome['mlp_pred'] = pullm_mlp.predict(pullm_x_test)
pullm_pred_outcome['vcf_prob'] = pd.DataFrame(pullm_vcf_pred_probs)
pullm_pred_outcome['vcf_pred'] = pullm_vcf.predict(pullm_x_test)
pullm_pred_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\pullm\\pullm_frsh_pred_outcome.csv', encoding='utf-8', index=False)

#%%
# Vancouver predicted outcome
vanco_pred_outcome['lr_prob'] = pd.DataFrame(vanco_lreg_pred_probs)
vanco_pred_outcome['lr_pred'] = vanco_lreg.predict(vanco_x_test)
vanco_pred_outcome['sgd_prob'] = pd.DataFrame(vanco_sgd_pred_probs)
vanco_pred_outcome['sgd_pred'] = vanco_sgd.predict(vanco_x_test)
vanco_pred_outcome['xgb_prob'] = pd.DataFrame(vanco_xgb_pred_probs)
vanco_pred_outcome['xgb_pred'] = vanco_xgb.predict(vanco_x_test)
# vanco_pred_outcome['mlp_prob'] = pd.DataFrame(vanco_mlp_pred_probs)
# vanco_pred_outcome['mlp_pred'] = vanco_mlp.predict(vanco_x_test)
vanco_pred_outcome['vcf_prob'] = pd.DataFrame(vanco_vcf_pred_probs)
vanco_pred_outcome['vcf_pred'] = vanco_vcf.predict(vanco_x_test)
vanco_pred_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\vanco\\vanco_frsh_pred_outcome.csv', encoding='utf-8', index=False)

#%%
# Tri-Cities predicted outcome
trici_pred_outcome['lr_prob'] = pd.DataFrame(trici_lreg_pred_probs)
trici_pred_outcome['lr_pred'] = trici_lreg.predict(trici_x_test)
trici_pred_outcome['sgd_prob'] = pd.DataFrame(trici_sgd_pred_probs)
trici_pred_outcome['sgd_pred'] = trici_sgd.predict(trici_x_test)
trici_pred_outcome['xgb_prob'] = pd.DataFrame(trici_xgb_pred_probs)
trici_pred_outcome['xgb_pred'] = trici_xgb.predict(trici_x_test)
# trici_pred_outcome['mlp_prob'] = pd.DataFrame(trici_mlp_pred_probs)
# trici_pred_outcome['mlp_pred'] = trici_mlp.predict(trici_x_test)
trici_pred_outcome['vcf_prob'] = pd.DataFrame(trici_vcf_pred_probs)
trici_pred_outcome['vcf_pred'] = trici_vcf.predict(trici_x_test)
trici_pred_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\trici\\trici_frsh_pred_outcome.csv', encoding='utf-8', index=False)

#%%
# University predicted outcome
univr_pred_outcome['lr_prob'] = pd.DataFrame(univr_lreg_pred_probs)
univr_pred_outcome['lr_pred'] = univr_lreg.predict(univr_x_test)
univr_pred_outcome['sgd_prob'] = pd.DataFrame(univr_sgd_pred_probs)
univr_pred_outcome['sgd_pred'] = univr_sgd.predict(univr_x_test)
univr_pred_outcome['xgb_prob'] = pd.DataFrame(univr_xgb_pred_probs)
univr_pred_outcome['xgb_pred'] = univr_xgb.predict(univr_x_test)
# univr_pred_outcome['mlp_prob'] = pd.DataFrame(univr_mlp_pred_probs)
# univr_pred_outcome['mlp_pred'] = univr_mlp.predict(univr_x_test)
univr_pred_outcome['vcf_prob'] = pd.DataFrame(univr_vcf_pred_probs)
univr_pred_outcome['vcf_pred'] = univr_vcf.predict(univr_x_test)
univr_pred_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\univr\\univr_frsh_pred_outcome.csv', encoding='utf-8', index=False)

#%%
# Pullman aggregate outcome
pullm_aggregate_outcome['emplid'] = pullm_aggregate_outcome['emplid'].astype(str).str.zfill(9)
pullm_aggregate_outcome['risk_prob'] = 1 - pd.DataFrame(pullm_vcf_pred_probs).round(4)

pullm_aggregate_outcome = pullm_aggregate_outcome.rename(columns={"male": "sex_ind"})
pullm_aggregate_outcome.loc[pullm_aggregate_outcome['sex_ind'] == 1, 'sex_descr'] = 'Male'
pullm_aggregate_outcome.loc[pullm_aggregate_outcome['sex_ind'] == 0, 'sex_descr'] = 'Female'

pullm_aggregate_outcome = pullm_aggregate_outcome.rename(columns={"underrep_minority": "underrep_minority_ind"})
pullm_aggregate_outcome.loc[pullm_aggregate_outcome['underrep_minority_ind'] == 1, 'underrep_minority_descr'] = 'Minority'
pullm_aggregate_outcome.loc[pullm_aggregate_outcome['underrep_minority_ind'] == 0, 'underrep_minority_descr'] = 'Non-minority'

pullm_aggregate_outcome = pullm_aggregate_outcome.rename(columns={"resident": "resident_ind"})
pullm_aggregate_outcome.loc[pullm_aggregate_outcome['resident_ind'] == 1, 'resident_descr'] = 'Resident'
pullm_aggregate_outcome.loc[pullm_aggregate_outcome['resident_ind'] == 0, 'resident_descr'] = 'non-Resident'

pullm_aggregate_outcome.loc[pullm_aggregate_outcome['first_gen_flag'] == 'Y', 'first_gen_flag'] = 1
pullm_aggregate_outcome.loc[pullm_aggregate_outcome['first_gen_flag'] == 'N', 'first_gen_flag'] = 0

pullm_aggregate_outcome = pullm_aggregate_outcome.rename(columns={"first_gen_flag": "first_gen_ind"})
pullm_aggregate_outcome.loc[pullm_aggregate_outcome['first_gen_ind'] == 1, 'first_gen_descr'] = 'non-First Gen'
pullm_aggregate_outcome.loc[pullm_aggregate_outcome['first_gen_ind'] == 0, 'first_gen_descr'] = 'First Gen'

pullm_aggregate_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\pullm\\pullm_frsh_aggregate_outcome.csv', encoding='utf-8', index=False)

#%%
# Vancouver aggregate outcome
vanco_aggregate_outcome['emplid'] = vanco_aggregate_outcome['emplid'].astype(str).str.zfill(9)
vanco_aggregate_outcome['risk_prob'] = 1 - pd.DataFrame(vanco_vcf_pred_probs).round(4)

vanco_aggregate_outcome = vanco_aggregate_outcome.rename(columns={"male": "sex_ind"})
vanco_aggregate_outcome.loc[vanco_aggregate_outcome['sex_ind'] == 1, 'sex_descr'] = 'Male'
vanco_aggregate_outcome.loc[vanco_aggregate_outcome['sex_ind'] == 0, 'sex_descr'] = 'Female'

vanco_aggregate_outcome = vanco_aggregate_outcome.rename(columns={"underrep_minority": "underrep_minority_ind"})
vanco_aggregate_outcome.loc[vanco_aggregate_outcome['underrep_minority_ind'] == 1, 'underrep_minority_descr'] = 'Minority'
vanco_aggregate_outcome.loc[vanco_aggregate_outcome['underrep_minority_ind'] == 0, 'underrep_minority_descr'] = 'Non-minority'

vanco_aggregate_outcome = vanco_aggregate_outcome.rename(columns={"resident": "resident_ind"})
vanco_aggregate_outcome.loc[vanco_aggregate_outcome['resident_ind'] == 1, 'resident_descr'] = 'Resident'
vanco_aggregate_outcome.loc[vanco_aggregate_outcome['resident_ind'] == 0, 'resident_descr'] = 'non-Resident'

vanco_aggregate_outcome.loc[vanco_aggregate_outcome['first_gen_flag'] == 'Y', 'first_gen_flag'] = 1
vanco_aggregate_outcome.loc[vanco_aggregate_outcome['first_gen_flag'] == 'N', 'first_gen_flag'] = 0

vanco_aggregate_outcome = vanco_aggregate_outcome.rename(columns={"first_gen_flag": "first_gen_ind"})
vanco_aggregate_outcome.loc[vanco_aggregate_outcome['first_gen_ind'] == 1, 'first_gen_descr'] = 'non-First Gen'
vanco_aggregate_outcome.loc[vanco_aggregate_outcome['first_gen_ind'] == 0, 'first_gen_descr'] = 'First Gen'

vanco_aggregate_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\vanco\\vanco_frsh_aggregate_outcome.csv', encoding='utf-8', index=False)

#%%
# Tri-Cities aggregate outcome
trici_aggregate_outcome['emplid'] = trici_aggregate_outcome['emplid'].astype(str).str.zfill(9)
trici_aggregate_outcome['risk_prob'] = 1 - pd.DataFrame(trici_vcf_pred_probs).round(4)

trici_aggregate_outcome = trici_aggregate_outcome.rename(columns={"male": "sex_ind"})
trici_aggregate_outcome.loc[trici_aggregate_outcome['sex_ind'] == 1, 'sex_descr'] = 'Male'
trici_aggregate_outcome.loc[trici_aggregate_outcome['sex_ind'] == 0, 'sex_descr'] = 'Female'

trici_aggregate_outcome = trici_aggregate_outcome.rename(columns={"underrep_minority": "underrep_minority_ind"})
trici_aggregate_outcome.loc[trici_aggregate_outcome['underrep_minority_ind'] == 1, 'underrep_minority_descr'] = 'Minority'
trici_aggregate_outcome.loc[trici_aggregate_outcome['underrep_minority_ind'] == 0, 'underrep_minority_descr'] = 'Non-minority'

trici_aggregate_outcome = trici_aggregate_outcome.rename(columns={"resident": "resident_ind"})
trici_aggregate_outcome.loc[trici_aggregate_outcome['resident_ind'] == 1, 'resident_descr'] = 'Resident'
trici_aggregate_outcome.loc[trici_aggregate_outcome['resident_ind'] == 0, 'resident_descr'] = 'non-Resident'

trici_aggregate_outcome.loc[trici_aggregate_outcome['first_gen_flag'] == 'Y', 'first_gen_flag'] = 1
trici_aggregate_outcome.loc[trici_aggregate_outcome['first_gen_flag'] == 'N', 'first_gen_flag'] = 0

trici_aggregate_outcome = trici_aggregate_outcome.rename(columns={"first_gen_flag": "first_gen_ind"})
trici_aggregate_outcome.loc[trici_aggregate_outcome['first_gen_ind'] == 1, 'first_gen_descr'] = 'non-First Gen'
trici_aggregate_outcome.loc[trici_aggregate_outcome['first_gen_ind'] == 0, 'first_gen_descr'] = 'First Gen'

trici_aggregate_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\trici\\trici_frsh_aggregate_outcome.csv', encoding='utf-8', index=False)

#%%
# University aggregate outcome
univr_aggregate_outcome['emplid'] = univr_aggregate_outcome['emplid'].astype(str).str.zfill(9)
univr_aggregate_outcome['risk_prob'] = 1 - pd.DataFrame(univr_vcf_pred_probs).round(4)

univr_aggregate_outcome = univr_aggregate_outcome.rename(columns={"male": "sex_ind"})
univr_aggregate_outcome.loc[univr_aggregate_outcome['sex_ind'] == 1, 'sex_descr'] = 'Male'
univr_aggregate_outcome.loc[univr_aggregate_outcome['sex_ind'] == 0, 'sex_descr'] = 'Female'

univr_aggregate_outcome = univr_aggregate_outcome.rename(columns={"underrep_minority": "underrep_minority_ind"})
univr_aggregate_outcome.loc[univr_aggregate_outcome['underrep_minority_ind'] == 1, 'underrep_minority_descr'] = 'Minority'
univr_aggregate_outcome.loc[univr_aggregate_outcome['underrep_minority_ind'] == 0, 'underrep_minority_descr'] = 'Non-minority'

univr_aggregate_outcome = univr_aggregate_outcome.rename(columns={"resident": "resident_ind"})
univr_aggregate_outcome.loc[univr_aggregate_outcome['resident_ind'] == 1, 'resident_descr'] = 'Resident'
univr_aggregate_outcome.loc[univr_aggregate_outcome['resident_ind'] == 0, 'resident_descr'] = 'non-Resident'

univr_aggregate_outcome.loc[univr_aggregate_outcome['first_gen_flag'] == 'Y', 'first_gen_flag'] = 1
univr_aggregate_outcome.loc[univr_aggregate_outcome['first_gen_flag'] == 'N', 'first_gen_flag'] = 0

univr_aggregate_outcome = univr_aggregate_outcome.rename(columns={"first_gen_flag": "first_gen_ind"})
univr_aggregate_outcome.loc[univr_aggregate_outcome['first_gen_ind'] == 1, 'first_gen_descr'] = 'non-First Gen'
univr_aggregate_outcome.loc[univr_aggregate_outcome['first_gen_ind'] == 0, 'first_gen_descr'] = 'First Gen'

univr_aggregate_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\univr\\univr_frsh_aggregate_outcome.csv', encoding='utf-8', index=False)

#%%
# Pullman current outcome
pullm_current_outcome['emplid'] = pullm_current_outcome['emplid'].astype(str).str.zfill(9)
pullm_current_outcome['risk_prob'] = 1 - pd.DataFrame(pullm_vcf_pred_probs).round(4)

pullm_current_outcome['date'] = run_date
pullm_current_outcome['model_id'] = model_id

#%%
# Vancouver current outcome
vanco_current_outcome['emplid'] = vanco_current_outcome['emplid'].astype(str).str.zfill(9)
vanco_current_outcome['risk_prob'] = 1 - pd.DataFrame(vanco_vcf_pred_probs).round(4)

vanco_current_outcome['date'] = run_date
vanco_current_outcome['model_id'] = model_id

#%%
# Tri-Cities current outcome
trici_current_outcome['emplid'] = trici_current_outcome['emplid'].astype(str).str.zfill(9)
trici_current_outcome['risk_prob'] = 1 - pd.DataFrame(trici_vcf_pred_probs).round(4)

trici_current_outcome['date'] = run_date
trici_current_outcome['model_id'] = model_id

#%%
# University current outcome
univr_current_outcome['emplid'] = univr_current_outcome['emplid'].astype(str).str.zfill(9)
univr_current_outcome['risk_prob'] = 1 - pd.DataFrame(univr_vcf_pred_probs).round(4)

univr_current_outcome['date'] = run_date
univr_current_outcome['model_id'] = model_id

#%%
# Pullman to csv and to sql
if not os.path.isfile('Z:\\Nathan\\Models\\student_risk\\predictions\\pullm\\pullm_frsh_student_outcome.csv'):
	pullm_current_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\pullm\\pullm_frsh_student_outcome.csv', encoding='utf-8', index=False)
	pullm_current_outcome.to_sql('student_outcome', con=auto_engine, if_exists='append', index=False, schema='oracle_int.dbo')
else:
	pullm_prior_outcome = pd.read_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\pullm\\pullm_frsh_student_outcome.csv', encoding='utf-8', low_memory=False)
	pullm_prior_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\pullm\\pullm_frsh_student_backup.csv', encoding='utf-8', index=False)
	pullm_student_outcome = pd.concat([pullm_prior_outcome, pullm_current_outcome])
	pullm_student_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\pullm\\pullm_frsh_student_outcome.csv', encoding='utf-8', index=False)
	pullm_current_outcome.to_sql('student_outcome', con=auto_engine, if_exists='append', index=False, schema='oracle_int.dbo')

#%%
# Vancouver to csv and to sql
if not os.path.isfile('Z:\\Nathan\\Models\\student_risk\\predictions\\vanco\\vanco_frsh_student_outcome.csv'):
	vanco_current_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\vanco\\vanco_frsh_student_outcome.csv', encoding='utf-8', index=False)
	vanco_current_outcome.to_sql('student_outcome', con=auto_engine, if_exists='append', index=False, schema='oracle_int.dbo')
else:
	vanco_prior_outcome = pd.read_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\vanco\\vanco_frsh_student_outcome.csv', encoding='utf-8', low_memory=False)
	vanco_prior_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\vanco\\vanco_frsh_student_backup.csv', encoding='utf-8', index=False)
	vanco_student_outcome = pd.concat([vanco_prior_outcome, vanco_current_outcome])
	vanco_student_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\vanco\\vanco_frsh_student_outcome.csv', encoding='utf-8', index=False)
	vanco_current_outcome.to_sql('student_outcome', con=auto_engine, if_exists='append', index=False, schema='oracle_int.dbo')

#%%
# Tri-Cities to csv and to sql
if not os.path.isfile('Z:\\Nathan\\Models\\student_risk\\predictions\\trici\\trici_frsh_student_outcome.csv'):
	trici_current_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\trici\\trici_frsh_student_outcome.csv', encoding='utf-8', index=False)
	trici_current_outcome.to_sql('student_outcome', con=auto_engine, if_exists='append', index=False, schema='oracle_int.dbo')
else:
	trici_prior_outcome = pd.read_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\trici\\trici_frsh_student_outcome.csv', encoding='utf-8', low_memory=False)
	trici_prior_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\trici\\trici_frsh_student_backup.csv', encoding='utf-8', index=False)
	trici_student_outcome = pd.concat([trici_prior_outcome, trici_current_outcome])
	trici_student_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\trici\\trici_frsh_student_outcome.csv', encoding='utf-8', index=False)
	trici_current_outcome.to_sql('student_outcome', con=auto_engine, if_exists='append', index=False, schema='oracle_int.dbo')

#%%
# University to csv and to sql
if not os.path.isfile('Z:\\Nathan\\Models\\student_risk\\predictions\\univr\\univr_frsh_student_outcome.csv'):
	univr_current_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\univr\\univr_frsh_student_outcome.csv', encoding='utf-8', index=False)
	univr_current_outcome.to_sql('student_outcome', con=auto_engine, if_exists='append', index=False, schema='oracle_int.dbo')
else:
	univr_prior_outcome = pd.read_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\univr\\univr_frsh_student_outcome.csv', encoding='utf-8', low_memory=False)
	univr_prior_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\univr\\univr_frsh_student_backup.csv', encoding='utf-8', index=False)
	univr_student_outcome = pd.concat([univr_prior_outcome, univr_current_outcome])
	univr_student_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\univr\\univr_frsh_student_outcome.csv', encoding='utf-8', index=False)
	univr_current_outcome.to_sql('student_outcome', con=auto_engine, if_exists='append', index=False, schema='oracle_int.dbo')

#%%
# Pullman top-N SHAP values to csv and to sql
if datetime.datetime.today().weekday() == day_of_week:

	pullm_shap_file = open('Z:\\Nathan\\Models\\student_risk\\shap\\pullm\\pullm_frsh_shap.csv', 'w', newline='')
	pullm_shap_writer = csv.writer(pullm_shap_file)
	pullm_shap_insert = []

	pullm_shap_writer.writerow(['emplid','shap_values'])

	for emplid in pullm_shap_zip:
		pullm_shap_writer.writerow([emplid, list(islice(pullm_shap_zip[emplid].items(), top_N))])
		pullm_shap_sql = [emplid, list(islice(pullm_shap_zip[emplid].items(), top_N))]
		
		pullm_shap_insert.append(str(pullm_shap_sql[0]).zfill(9))

		for index in range(top_N):
			shap_str, shap_float = pullm_shap_sql[1][index]
			pullm_shap_insert.append(shap_str) 
			pullm_shap_insert.append(round(shap_float, 4))

	pullm_shap_file.close()

	while pullm_shap_insert:
		ins = student_shap.insert().values(emplid=pullm_shap_insert.pop(0), 
											shap_descr_1=pullm_shap_insert.pop(0), shap_value_1=pullm_shap_insert.pop(0), 
											shap_descr_2=pullm_shap_insert.pop(0), shap_value_2=pullm_shap_insert.pop(0), 
											shap_descr_3=pullm_shap_insert.pop(0), shap_value_3=pullm_shap_insert.pop(0), 
											shap_descr_4=pullm_shap_insert.pop(0), shap_value_4=pullm_shap_insert.pop(0), 
											shap_descr_5=pullm_shap_insert.pop(0), shap_value_5=pullm_shap_insert.pop(0), 
											date=run_date, model_id=model_id)
		engine.execute(ins)

#%%
# Vancouver top-N SHAP values to csv and to sql
	vanco_shap_file = open('Z:\\Nathan\\Models\\student_risk\\shap\\vanco\\vanco_frsh_shap.csv', 'w', newline='')
	vanco_shap_writer = csv.writer(vanco_shap_file)
	vanco_shap_insert = []

	vanco_shap_writer.writerow(['emplid','shap_values'])

	for emplid in vanco_shap_zip:
		vanco_shap_writer.writerow([emplid, list(islice(vanco_shap_zip[emplid].items(), top_N))])
		vanco_shap_sql = [emplid, list(islice(vanco_shap_zip[emplid].items(), top_N))]
		
		vanco_shap_insert.append(str(vanco_shap_sql[0]).zfill(9))

		for index in range(top_N):
			shap_str, shap_float = vanco_shap_sql[1][index]
			vanco_shap_insert.append(shap_str) 
			vanco_shap_insert.append(round(shap_float, 4))

	vanco_shap_file.close()

	while vanco_shap_insert:
		ins = student_shap.insert().values(emplid=vanco_shap_insert.pop(0), 
											shap_descr_1=vanco_shap_insert.pop(0), shap_value_1=vanco_shap_insert.pop(0), 
											shap_descr_2=vanco_shap_insert.pop(0), shap_value_2=vanco_shap_insert.pop(0), 
											shap_descr_3=vanco_shap_insert.pop(0), shap_value_3=vanco_shap_insert.pop(0), 
											shap_descr_4=vanco_shap_insert.pop(0), shap_value_4=vanco_shap_insert.pop(0), 
											shap_descr_5=vanco_shap_insert.pop(0), shap_value_5=vanco_shap_insert.pop(0), 
											date=run_date, model_id=model_id)
		engine.execute(ins)

#%%
# Tri-Cities top-N SHAP values to csv and to sql
	trici_shap_file = open('Z:\\Nathan\\Models\\student_risk\\shap\\trici\\trici_frsh_shap.csv', 'w', newline='')
	trici_shap_writer = csv.writer(trici_shap_file)
	trici_shap_insert = []

	trici_shap_writer.writerow(['emplid','shap_values'])

	for emplid in trici_shap_zip:
		trici_shap_writer.writerow([emplid, list(islice(trici_shap_zip[emplid].items(), top_N))])
		trici_shap_sql = [emplid, list(islice(trici_shap_zip[emplid].items(), top_N))]
		
		trici_shap_insert.append(str(trici_shap_sql[0]).zfill(9))

		for index in range(top_N):
			shap_str, shap_float = trici_shap_sql[1][index]
			trici_shap_insert.append(shap_str) 
			trici_shap_insert.append(round(shap_float, 4))

	trici_shap_file.close()

	while trici_shap_insert:
		ins = student_shap.insert().values(emplid=trici_shap_insert.pop(0), 
											shap_descr_1=trici_shap_insert.pop(0), shap_value_1=trici_shap_insert.pop(0), 
											shap_descr_2=trici_shap_insert.pop(0), shap_value_2=trici_shap_insert.pop(0), 
											shap_descr_3=trici_shap_insert.pop(0), shap_value_3=trici_shap_insert.pop(0), 
											shap_descr_4=trici_shap_insert.pop(0), shap_value_4=trici_shap_insert.pop(0), 
											shap_descr_5=trici_shap_insert.pop(0), shap_value_5=trici_shap_insert.pop(0), 
											date=run_date, model_id=model_id)
		engine.execute(ins)

#%%
# University top-N SHAP values to csv and to sql
	univr_shap_file = open('Z:\\Nathan\\Models\\student_risk\\shap\\trici\\univr_frsh_shap.csv', 'w', newline='')
	univr_shap_writer = csv.writer(univr_shap_file)
	univr_shap_insert = []

	univr_shap_writer.writerow(['emplid','shap_values'])

	for emplid in univr_shap_zip:
		univr_shap_writer.writerow([emplid, list(islice(univr_shap_zip[emplid].items(), top_N))])
		univr_shap_sql = [emplid, list(islice(univr_shap_zip[emplid].items(), top_N))]
		
		univr_shap_insert.append(str(univr_shap_sql[0]).zfill(9))

		for index in range(top_N):
			shap_str, shap_float = univr_shap_sql[1][index]
			univr_shap_insert.append(shap_str) 
			univr_shap_insert.append(round(shap_float, 4))

	univr_shap_file.close()

	while univr_shap_insert:
		ins = student_shap.insert().values(emplid=univr_shap_insert.pop(0), 
											shap_descr_1=univr_shap_insert.pop(0), shap_value_1=univr_shap_insert.pop(0), 
											shap_descr_2=univr_shap_insert.pop(0), shap_value_2=univr_shap_insert.pop(0), 
											shap_descr_3=univr_shap_insert.pop(0), shap_value_3=univr_shap_insert.pop(0), 
											shap_descr_4=univr_shap_insert.pop(0), shap_value_4=univr_shap_insert.pop(0), 
											shap_descr_5=univr_shap_insert.pop(0), shap_value_5=univr_shap_insert.pop(0), 
											date=run_date, model_id=model_id)
		engine.execute(ins)

#%%
# Output model

# Pullman model output
joblib.dump(pullm_vcf, f'Z:\\Nathan\\Models\\student_risk\\models\\pullm_frsh_model_v{sklearn.__version__}.pkl')

#%%
# Vancouver model output
joblib.dump(vanco_vcf, f'Z:\\Nathan\\Models\\student_risk\\models\\vanco_frsh_model_v{sklearn.__version__}.pkl')

#%%
# Tri-Cities model output
joblib.dump(trici_vcf, f'Z:\\Nathan\\Models\\student_risk\\models\\trici_frsh_model_v{sklearn.__version__}.pkl')

#%%
# University model output
joblib.dump(univr_vcf, f'Z:\\Nathan\\Models\\student_risk\\models\\univr_frsh_model_v{sklearn.__version__}.pkl')

print('Done\n')
