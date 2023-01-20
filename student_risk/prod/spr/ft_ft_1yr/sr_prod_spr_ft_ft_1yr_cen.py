#%%
import csv
import datetime
import os
import pathlib
import time
import urllib
from datetime import date
from itertools import islice

import gower
import joblib
import numpy as np
import pandas as pd
import pyodbc
import saspy
import sklearn
import sqlalchemy
from imblearn.under_sampling import NearMiss, TomekLinks
from patsy import dmatrices
from sklearn.compose import make_column_transformer
from sklearn.ensemble import VotingClassifier
from sklearn.experimental import enable_halving_search_cv
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.model_selection import HalvingGridSearchCV, train_test_split
from sklearn.neighbors import LocalOutlierFactor
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sqlalchemy import MetaData, Table
from statsmodels.discrete.discrete_model import Logit
from statsmodels.stats.outliers_influence import variance_inflation_factor
from xgboost import XGBClassifier, XGBRFClassifier

import shap
from student_risk import build_ft_ft_1yr_prod, config

#%%
# Database connection
cred = pathlib.Path('Z:\\Nathan\\Models\\student_risk\\login.bin').read_text().split('|')
params = urllib.parse.quote_plus(f'TRUSTED_CONNECTION=YES; DRIVER={{SQL Server Native Client 11.0}}; SERVER={cred[0]}; DATABASE={cred[1]}')
engine = sqlalchemy.create_engine(f'mssql+pyodbc:///?odbc_connect={params}')
auto_engine = engine.execution_options(autocommit=True, isolation_level='AUTOCOMMIT')
metadata_engine = MetaData(engine.execution_options(autocommit=True, isolation_level='AUTOCOMMIT'))
student_shap = Table('student_shap', metadata_engine, autoload=True)

#%%
# Global variable initializaiton
strm = None
top_N = 5
model_id = 5
run_date = date.today()
unwanted_vars = ['emplid','enrl_ind']

#%%
# Global XGBoost hyperparameter initialization
min_child_weight = 6
max_bin = 32
num_parallel_tree = 64
subsample = 0.8
colsample_bytree = 0.8
colsample_bynode = 0.8
verbose = False

#%%
# Census date and snapshot check 
calendar = pd.read_csv('Z:\\Nathan\\Models\\student_risk\\supplemental_files\\acad_calendar.csv', encoding='utf-8', parse_dates=['term_begin_dt', 'midterm_begin_dt', 'term_end_dt']).fillna(9999)

now = datetime.datetime.now()
now_dt = datetime.datetime.strptime(f'{now.month:02}-{now.day:02}-{now.year:04}', '%m-%d-%Y')

now_day = now.day
now_month = now.month
now_year = now.year

strm = calendar[(calendar['term_begin_dt'] <= now_dt) & (calendar['term_end_dt'] >= now_dt)]['STRM'].values[0]

census_day = calendar[(calendar['term_begin_dt'] <= now_dt) & (calendar['term_end_dt'] >= now_dt)]['census_day'].values[0]
census_month = calendar[(calendar['term_begin_dt'] <= now_dt) & (calendar['term_end_dt'] >= now_dt)]['census_month'].values[0]
census_year = calendar[(calendar['term_begin_dt'] <= now_dt) & (calendar['term_end_dt'] >= now_dt)]['census_year'].values[0]

if now_year < census_year:
	raise config.CenError(f'{run_date}: Census year exception, attempting to run if census newest snapshot.')

elif (now_year == census_year and now_month < census_month):
	raise config.CenError(f'{run_date}: Census month exception, attempting to run if census newest snapshot.')

elif (now_year == census_year and now_month == census_month and now_day < census_day):
	raise config.CenError(f'{run_date}: Census day exception, attempting to run if census newest snapshot.')

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

	if snap_check != 1:
		raise config.CenError(f'{date.today()}: No census date exception but snapshot exception, attempting to run from precensus.')

	else:
		print(f'{date.today()}: No census date or snapshot exceptions, running from census.')

#%%
# SAS dataset builder
build_ft_ft_1yr_prod.DatasetBuilderProd.build_census_prod()

#%%
# Import pre-split data
validation_set = pd.read_sas('Z:\\Nathan\\Models\\student_risk\\datasets\\ft_ft_1yr_validation_set.sas7bdat', encoding='latin1')
training_set = pd.read_sas('Z:\\Nathan\\Models\\student_risk\\datasets\\ft_ft_1yr_training_set.sas7bdat', encoding='latin1')
testing_set = pd.read_sas('Z:\\Nathan\\Models\\student_risk\\datasets\\ft_ft_1yr_testing_set.sas7bdat', encoding='latin1')

#%%
# Prepare dataframes
print('\nPrepare dataframes and preprocess data...')

# Pullman variables
pullm_data_vars = [
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
# 'count_week_from_term_begin_dt',
# 'marital_status',
# 'acs_mi',
# 'distance',
# 'pop_dens',
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
# 'high_school_gpa',
'fall_term_gpa',
'fall_term_gpa_mi',
'fall_term_D_grade_count',
'fall_term_F_grade_count',
# 'fall_term_S_grade_count',
# 'fall_term_W_grade_count',
# 'spring_midterm_gpa_change',
# 'awe_instrument',
# 'cdi_instrument',
# 'fall_avg_difficulty',
# 'fall_avg_pct_withdrawn',
# 'fall_avg_pct_CDFW',
# 'fall_avg_pct_CDF',
# 'fall_avg_pct_DFW',
# 'fall_avg_pct_DF',
'spring_avg_difficulty',
'spring_avg_pct_withdrawn',
# 'spring_avg_pct_CDFW',
'spring_avg_pct_CDF',
# 'spring_avg_pct_DFW',
# 'spring_avg_pct_DF',
# 'fall_lec_count',
# 'fall_lab_count',
# 'fall_lec_contact_hrs',
# 'fall_lab_contact_hrs',
'spring_lec_count',
'spring_lab_count',
'spring_stu_count',
'spring_oth_count',
# 'spring_lec_contact_hrs',
# 'spring_lab_contact_hrs',
# 'total_fall_contact_hrs',
# 'total_spring_contact_hrs',
# 'fall_midterm_gpa_avg',
# 'fall_midterm_gpa_avg_ind',
# 'spring_midterm_gpa_avg',
# 'spring_midterm_gpa_avg_ind',
'cum_adj_transfer_hours',
'resident',
# 'father_wsu_flag',
# 'mother_wsu_flag',
'parent1_highest_educ_lvl',
'parent2_highest_educ_lvl',
# 'citizenship_country',
# 'gini_indx',
# 'pvrt_rate',
# 'median_inc',
# 'median_value',
# 'educ_rate',
# 'pct_blk',
# 'pct_ai',
# 'pct_asn',
# 'pct_hawi',
# 'pct_oth',
# 'pct_two',
# 'pct_non',
# 'pct_hisp',
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
'spring_credit_hours',
# 'total_spring_units',
'spring_withdrawn_hours',
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
]

pullm_x_vars = [x for x in pullm_data_vars if x not in unwanted_vars]

# Pullman dataframes
pullm_logit_df = training_set[(training_set['adj_acad_prog_primary_campus'] == 'PULLM') 
								& (training_set['adj_admit_type_cat'] == 'FRSH')][pullm_data_vars].dropna().drop(columns=['emplid'])

pullm_validation_set = validation_set[(validation_set['adj_acad_prog_primary_campus'] == 'PULLM') 
								& (validation_set['adj_admit_type_cat'] == 'FRSH')][pullm_data_vars].dropna()

pullm_training_set = training_set[(training_set['adj_acad_prog_primary_campus'] == 'PULLM') 
								& (training_set['adj_admit_type_cat'] == 'FRSH')][pullm_data_vars].dropna()

pullm_testing_set = testing_set[(testing_set['adj_acad_prog_primary_campus'] == 'PULLM') 
								& (testing_set['adj_admit_type_cat'] == 'FRSH')][pullm_data_vars].dropna().drop(columns=['enrl_ind'])

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
# Vancouver variables
vanco_data_vars = [
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
# 'count_week_from_term_begin_dt',
# 'marital_status',
# 'acs_mi',
# 'distance',
# 'pop_dens',
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
# 'high_school_gpa',
'fall_term_gpa',
'fall_term_gpa_mi',
'fall_term_D_grade_count',
'fall_term_F_grade_count',
# 'fall_term_S_grade_count',
# 'fall_term_W_grade_count',
# 'spring_midterm_gpa_change',
# 'awe_instrument',
# 'cdi_instrument',
# 'fall_avg_difficulty',
# 'fall_avg_pct_withdrawn',
# 'fall_avg_pct_CDFW',
# 'fall_avg_pct_CDF',
# 'fall_avg_pct_DFW',
# 'fall_avg_pct_DF',
'spring_avg_difficulty',
'spring_avg_pct_withdrawn',
# 'spring_avg_pct_CDFW',
'spring_avg_pct_CDF',
# 'spring_avg_pct_DFW',
# 'spring_avg_pct_DF',
# 'fall_lec_count',
# 'fall_lab_count',
# 'fall_lec_contact_hrs',
# 'fall_lab_contact_hrs',
'spring_lec_count',
'spring_lab_count',
# 'spring_lec_contact_hrs',
# 'spring_lab_contact_hrs',
# 'total_fall_contact_hrs',
# 'total_spring_contact_hrs',
# 'fall_midterm_gpa_avg',
# 'fall_midterm_gpa_avg_ind',
# 'spring_midterm_gpa_avg',
# 'spring_midterm_gpa_avg_ind',
'cum_adj_transfer_hours',
'resident',
# 'father_wsu_flag',
# 'mother_wsu_flag',
'parent1_highest_educ_lvl',
'parent2_highest_educ_lvl',
# 'citizenship_country',
# 'gini_indx',
# 'pvrt_rate',
# 'median_inc',
# 'median_value',
# 'educ_rate',
# 'pct_blk',
# 'pct_ai',
# 'pct_asn',
# 'pct_hawi',
# 'pct_oth',
# 'pct_two',
# 'pct_non',
# 'pct_hisp',
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
'spring_credit_hours',
# 'total_spring_units',
'spring_withdrawn_hours',
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
]

vanco_x_vars = [x for x in vanco_data_vars if x not in unwanted_vars]

# Vancouver dataframes
vanco_logit_df = training_set[(training_set['adj_acad_prog_primary_campus'] == 'VANCO') 
								& (training_set['adj_admit_type_cat'] == 'FRSH')][vanco_data_vars].dropna().drop(columns=['emplid'])

vanco_validation_set = validation_set[(validation_set['adj_acad_prog_primary_campus'] == 'VANCO') 
								& (validation_set['adj_admit_type_cat'] == 'FRSH')][vanco_data_vars].dropna()

vanco_training_set = training_set[(training_set['adj_acad_prog_primary_campus'] == 'VANCO') 
								& (training_set['adj_admit_type_cat'] == 'FRSH')][vanco_data_vars].dropna()

vanco_testing_set = testing_set[(testing_set['adj_acad_prog_primary_campus'] == 'VANCO') 
								& (testing_set['adj_admit_type_cat'] == 'FRSH')][vanco_data_vars].dropna().drop(columns=['enrl_ind'])

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
# Tri-Cities variables
trici_data_vars = [
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
# 'count_week_from_term_begin_dt',
# 'marital_status',
# 'acs_mi',
# 'distance',
# 'pop_dens',
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
# 'high_school_gpa',
'fall_term_gpa',
'fall_term_gpa_mi',
'fall_term_D_grade_count',
'fall_term_F_grade_count',
# 'fall_term_S_grade_count',
# 'fall_term_W_grade_count',
# 'spring_midterm_gpa_change',
# 'awe_instrument',
# 'cdi_instrument',
# 'fall_avg_difficulty',
# 'fall_avg_pct_withdrawn',
# 'fall_avg_pct_CDFW',
# 'fall_avg_pct_CDF',
# 'fall_avg_pct_DFW',
# 'fall_avg_pct_DF',
'spring_avg_difficulty',
'spring_avg_pct_withdrawn',
# 'spring_avg_pct_CDFW',
'spring_avg_pct_CDF',
# 'spring_avg_pct_DFW',
# 'spring_avg_pct_DF',
# 'fall_lec_count',
# 'fall_lab_count',
# 'fall_lec_contact_hrs',
# 'fall_lab_contact_hrs',
'spring_lec_count',
'spring_lab_count',
# 'spring_lec_contact_hrs',
# 'spring_lab_contact_hrs',
# 'total_fall_contact_hrs',
# 'total_spring_contact_hrs',
# 'fall_midterm_gpa_avg',
# 'fall_midterm_gpa_avg_ind',
# 'spring_midterm_gpa_avg',
# 'spring_midterm_gpa_avg_ind',
'cum_adj_transfer_hours',
'resident',
# 'father_wsu_flag',
# 'mother_wsu_flag',
'parent1_highest_educ_lvl',
'parent2_highest_educ_lvl',
# 'citizenship_country',
# 'gini_indx',
# 'pvrt_rate',
# 'median_inc',
# 'median_value',
# 'educ_rate',
# 'pct_blk',
# 'pct_ai',
# 'pct_asn',
# 'pct_hawi',
# 'pct_oth',
# 'pct_two',
# 'pct_non',
# 'pct_hisp',
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
'spring_credit_hours',
# 'total_spring_units',
'spring_withdrawn_hours',
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
]

trici_x_vars = [x for x in trici_data_vars if x not in unwanted_vars]

# Tri-Cities dataframes
trici_logit_df = training_set[(training_set['adj_acad_prog_primary_campus'] == 'TRICI') 
								& (training_set['adj_admit_type_cat'] == 'FRSH')][trici_data_vars].dropna().drop(columns=['emplid'])

trici_validation_set = validation_set[(validation_set['adj_acad_prog_primary_campus'] == 'TRICI') 
								& (validation_set['adj_admit_type_cat'] == 'FRSH')][trici_data_vars].dropna()

trici_training_set = training_set[(training_set['adj_acad_prog_primary_campus'] == 'TRICI') 
								& (training_set['adj_admit_type_cat'] == 'FRSH')][trici_data_vars].dropna()

trici_testing_set = testing_set[(testing_set['adj_acad_prog_primary_campus'] == 'TRICI') 
								& (testing_set['adj_admit_type_cat'] == 'FRSH')][trici_data_vars].dropna().drop(columns=['enrl_ind'])
								
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
# University variables
univr_data_vars = [
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
# 'count_week_from_term_begin_dt',
# 'marital_status',
# 'acs_mi',
# 'distance',
# 'pop_dens',
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
# 'high_school_gpa',
'fall_term_gpa',
'fall_term_gpa_mi',
'fall_term_D_grade_count',
'fall_term_F_grade_count',
# 'fall_term_S_grade_count',
# 'fall_term_W_grade_count',
# 'spring_midterm_gpa_change',
# 'awe_instrument',
# 'cdi_instrument',
# 'fall_avg_difficulty',
# 'fall_avg_pct_withdrawn',
# 'fall_avg_pct_CDFW',
# 'fall_avg_pct_CDF',
# 'fall_avg_pct_DFW',
# 'fall_avg_pct_DF',
'spring_avg_difficulty',
'spring_avg_pct_withdrawn',
# 'spring_avg_pct_CDFW',
'spring_avg_pct_CDF',
# 'spring_avg_pct_DFW',
# 'spring_avg_pct_DF',
# 'fall_lec_count',
# 'fall_lab_count',
# 'fall_lec_contact_hrs',
# 'fall_lab_contact_hrs',
'spring_lec_count',
'spring_lab_count',
# 'spring_lec_contact_hrs',
# 'spring_lab_contact_hrs',
# 'total_fall_contact_hrs',
# 'total_spring_contact_hrs',
# 'fall_midterm_gpa_avg',
# 'fall_midterm_gpa_avg_ind',
# 'spring_midterm_gpa_avg',
# 'spring_midterm_gpa_avg_ind',
'cum_adj_transfer_hours',
'resident',
# 'father_wsu_flag',
# 'mother_wsu_flag',
'parent1_highest_educ_lvl',
'parent2_highest_educ_lvl',
# 'citizenship_country',
# 'gini_indx',
# 'pvrt_rate',
# 'median_inc',
# 'median_value',
# 'educ_rate',
# 'pct_blk',
# 'pct_ai',
# 'pct_asn',
# 'pct_hawi',
# 'pct_oth',
# 'pct_two',
# 'pct_non',
# 'pct_hisp',
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
'spring_credit_hours',
# 'total_spring_units',
'spring_withdrawn_hours',
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
]

univr_x_vars = [x for x in univr_data_vars if x not in unwanted_vars]

# University dataframes
univr_logit_df = training_set[(training_set['adj_admit_type_cat'] == 'FRSH')][univr_data_vars].dropna().drop(columns=['emplid'])

univr_validation_set = validation_set[(validation_set['adj_admit_type_cat'] == 'FRSH')][univr_data_vars].dropna()

univr_training_set = training_set[(training_set['adj_admit_type_cat'] == 'FRSH')][univr_data_vars].dropna()

univr_testing_set = testing_set[((testing_set['adj_acad_prog_primary_campus'] == 'EVERE') 
								& (testing_set['adj_admit_type_cat'] == 'FRSH')) 
								| ((testing_set['adj_acad_prog_primary_campus'] == 'SPOKA') 
								& (testing_set['adj_admit_type_cat'] == 'FRSH')) 
								| ((testing_set['adj_acad_prog_primary_campus'] == 'ONLIN') 
								& (testing_set['adj_admit_type_cat'] == 'FRSH'))][univr_data_vars].dropna().drop(columns=['enrl_ind'])

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
pullm_x_training_outlier = pullm_training_set.drop(columns=['enrl_ind','emplid'])
pullm_x_validation_outlier = pullm_validation_set.drop(columns=['enrl_ind','emplid'])

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

pullm_x_training_outlier = pullm_outlier_prep.fit_transform(pullm_x_training_outlier)
pullm_x_validation_outlier = pullm_outlier_prep.transform(pullm_x_validation_outlier)

pullm_x_training_gower = gower.gower_matrix(pullm_x_training_outlier)
pullm_x_validation_gower = gower.gower_matrix(pullm_x_validation_outlier)

pullm_training_set['mask'] = LocalOutlierFactor(metric='precomputed', n_jobs=-1).fit_predict(pullm_x_training_gower)
pullm_validation_set['mask'] = LocalOutlierFactor(metric='precomputed', n_jobs=-1).fit_predict(pullm_x_validation_gower)

pullm_training_outlier_set = pullm_training_set.drop(pullm_training_set[pullm_training_set['mask'] == 1].index)
pullm_training_outlier_set.to_csv('Z:\\Nathan\\Models\\student_risk\\outliers\\pullm_frst_training_outlier_set.csv', encoding='utf-8', index=False)
pullm_validation_outlier_set = pullm_validation_set.drop(pullm_validation_set[pullm_validation_set['mask'] == 1].index)
pullm_validation_outlier_set.to_csv('Z:\\Nathan\\Models\\student_risk\\outliers\\pullm_frst_validation_outlier_set.csv', encoding='utf-8', index=False)

pullm_training_set = pullm_training_set.drop(pullm_training_set[pullm_training_set['mask'] == -1].index)
pullm_training_set = pullm_training_set.drop(columns='mask')
pullm_validation_set = pullm_validation_set.drop(pullm_validation_set[pullm_validation_set['mask'] == -1].index)
pullm_validation_set = pullm_validation_set.drop(columns='mask')

#%%
# Vancouver outliers
vanco_x_training_outlier = vanco_training_set.drop(columns=['enrl_ind','emplid'])
vanco_x_validation_outlier = vanco_validation_set.drop(columns=['enrl_ind','emplid'])

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

vanco_x_training_outlier = vanco_outlier_prep.fit_transform(vanco_x_training_outlier)
vanco_x_validation_outlier = vanco_outlier_prep.transform(vanco_x_validation_outlier)

vanco_x_training_gower = gower.gower_matrix(vanco_x_training_outlier)
vanco_x_validation_gower = gower.gower_matrix(vanco_x_validation_outlier)

vanco_training_set['mask'] = LocalOutlierFactor(metric='precomputed', n_jobs=-1).fit_predict(vanco_x_training_gower)
vanco_validation_set['mask'] = LocalOutlierFactor(metric='precomputed', n_jobs=-1).fit_predict(vanco_x_validation_gower)

vanco_training_outlier_set = vanco_training_set.drop(vanco_training_set[vanco_training_set['mask'] == 1].index)
vanco_training_outlier_set.to_csv('Z:\\Nathan\\Models\\student_risk\\outliers\\vanco_frst_training_outlier_set.csv', encoding='utf-8', index=False)
vanco_validation_outlier_set = vanco_validation_set.drop(vanco_validation_set[vanco_validation_set['mask'] == 1].index)
vanco_validation_outlier_set.to_csv('Z:\\Nathan\\Models\\student_risk\\outliers\\vanco_frst_validation_outlier_set.csv', encoding='utf-8', index=False)

vanco_training_set = vanco_training_set.drop(vanco_training_set[vanco_training_set['mask'] == -1].index)
vanco_training_set = vanco_training_set.drop(columns='mask')
vanco_validation_set = vanco_validation_set.drop(vanco_validation_set[vanco_validation_set['mask'] == -1].index)
vanco_validation_set = vanco_validation_set.drop(columns='mask')

#%%
# Tri-Cities outliers
trici_x_training_outlier = trici_training_set.drop(columns=['enrl_ind','emplid'])
trici_x_validation_outlier = trici_validation_set.drop(columns=['enrl_ind','emplid'])

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

trici_x_training_outlier = trici_outlier_prep.fit_transform(trici_x_training_outlier)
trici_x_validation_outlier = trici_outlier_prep.transform(trici_x_validation_outlier)

trici_x_training_gower = gower.gower_matrix(trici_x_training_outlier)
trici_x_validation_gower = gower.gower_matrix(trici_x_validation_outlier)

trici_training_set['mask'] = LocalOutlierFactor(metric='precomputed', n_jobs=-1).fit_predict(trici_x_training_gower)
trici_validation_set['mask'] = LocalOutlierFactor(metric='precomputed', n_jobs=-1).fit_predict(trici_x_validation_gower)

trici_training_outlier_set = trici_training_set.drop(trici_training_set[trici_training_set['mask'] == 1].index)
trici_training_outlier_set.to_csv('Z:\\Nathan\\Models\\student_risk\\outliers\\trici_frst_training_outlier_set.csv', encoding='utf-8', index=False)
trici_validation_outlier_set = trici_validation_set.drop(trici_validation_set[trici_validation_set['mask'] == 1].index)
trici_validation_outlier_set.to_csv('Z:\\Nathan\\Models\\student_risk\\outliers\\trici_frst_validation_outlier_set.csv', encoding='utf-8', index=False)

trici_training_set = trici_training_set.drop(trici_training_set[trici_training_set['mask'] == -1].index)
trici_training_set = trici_training_set.drop(columns='mask')
trici_validation_set = trici_validation_set.drop(trici_validation_set[trici_validation_set['mask'] == -1].index)
trici_validation_set = trici_validation_set.drop(columns='mask')

#%%
# University outliers
univr_x_training_outlier = univr_training_set.drop(columns=['enrl_ind','emplid'])
univr_x_validation_outlier = univr_validation_set.drop(columns=['enrl_ind','emplid'])

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

univr_x_training_outlier = univr_outlier_prep.fit_transform(univr_x_training_outlier)
univr_x_validation_outlier = univr_outlier_prep.transform(univr_x_validation_outlier)

univr_x_training_gower = gower.gower_matrix(univr_x_training_outlier)
univr_x_validation_gower = gower.gower_matrix(univr_x_validation_outlier)

univr_training_set['mask'] = LocalOutlierFactor(metric='precomputed', n_jobs=-1).fit_predict(univr_x_training_gower)
univr_validation_set['mask'] = LocalOutlierFactor(metric='precomputed', n_jobs=-1).fit_predict(univr_x_validation_gower)

univr_training_outlier_set = univr_training_set.drop(univr_training_set[univr_training_set['mask'] == 1].index)
univr_training_outlier_set.to_csv('Z:\\Nathan\\Models\\student_risk\\outliers\\univr_frst_training_outlier_set.csv', encoding='utf-8', index=False)
univr_validation_outlier_set = univr_validation_set.drop(univr_validation_set[univr_validation_set['mask'] == 1].index)
univr_validation_outlier_set.to_csv('Z:\\Nathan\\Models\\student_risk\\outliers\\univr_frst_validation_outlier_set.csv', encoding='utf-8', index=False)

univr_training_set = univr_training_set.drop(univr_training_set[univr_training_set['mask'] == -1].index)
univr_training_set = univr_training_set.drop(columns='mask')
univr_validation_set = univr_validation_set.drop(univr_validation_set[univr_validation_set['mask'] == -1].index)
univr_validation_set = univr_validation_set.drop(columns='mask')

#%%
# Create Tomek Link undersampled validation and training sets

# Pullman undersample
pullm_x_train = pullm_training_set.drop(columns=['enrl_ind','emplid'])
pullm_x_cv = pullm_validation_set.drop(columns=['enrl_ind','emplid'])

pullm_x_test = pullm_testing_set[pullm_x_vars]

pullm_y_train = pullm_training_set['enrl_ind']
pullm_y_cv = pullm_validation_set['enrl_ind']
# pullm_y_test = pullm_testing_set['enrl_ind']

pullm_tomek_prep = make_column_transformer(
	# (StandardScaler(), [
	# 					'distance',
	# 					# 'age',
	# 					# 'min_week_from_term_begin_dt',
	# 					# 'max_week_from_term_begin_dt',
	# 					'count_week_from_term_begin_dt',
	# 					# 'sat_erws',
	# 					# 'sat_mss',
	# 					# 'sat_comp',
	# 					# 'attendee_total_visits',
	# 					'pop_dens', 
	# 					# 'qvalue', 
	# 					# 'gini_indx',
	# 					'median_inc',
	# 					# 'pvrt_rate',
	# 					'median_value',
	# 					# 'educ_rate',
	# 					# 'pct_blk',
	# 					# 'pct_ai',
	# 					# 'pct_asn',
	# 					# 'pct_hawi',
	# 					# 'pct_oth',
	# 					# 'pct_two',
	# 					# 'pct_non',
	# 					# 'pct_hisp',
	# 					# 'term_credit_hours',
	# 					'high_school_gpa',
	# 					# 'awe_instrument',
	# 					# 'cdi_instrument',
	# 					'fall_avg_difficulty',
	# 					# 'fall_avg_pct_withdrawn',
	# 					# 'fall_avg_pct_CDFW',
	# 					# 'fall_avg_pct_CDF',
	# 					'fall_lec_count',
	# 					'fall_lab_count',
	# 					# 'fall_int_count',
	# 					'fall_stu_count',
	# 					# 'fall_sem_count',
	# 					'fall_oth_count',
	# 					'fall_lec_contact_hrs',
	# 					'fall_lab_contact_hrs',
	# 					# 'fall_int_contact_hrs',
	# 					'fall_stu_contact_hrs',
	# 					# 'fall_sem_contact_hrs',
	# 					'fall_oth_contact_hrs',
	# 					# 'total_fall_contact_hrs',
	# 					'total_fall_units',
	# 					'fall_withdrawn_hours',
	# 					'cum_adj_transfer_hours',
	# 					# 'term_credit_hours',
	# 					# 'fed_efc',
	# 					# 'fed_need', 
	# 					'unmet_need_ofr'
	# 					]),
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
pullm_x_cv = pullm_tomek_prep.transform(pullm_x_cv)
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

pullm_under_train = TomekLinks(sampling_strategy='all', n_jobs=-1)
pullm_under_valid = TomekLinks(sampling_strategy='all', n_jobs=-1)

pullm_x_train, pullm_y_train = pullm_under_train.fit_resample(pullm_x_train, pullm_y_train)
pullm_x_cv, pullm_y_cv = pullm_under_valid.fit_resample(pullm_x_cv, pullm_y_cv)

pullm_tomek_train_index = pullm_under_train.sample_indices_
pullm_tomek_valid_index = pullm_under_valid.sample_indices_
pullm_training_set = pullm_training_set.reset_index(drop=True)
pullm_validation_set = pullm_validation_set.reset_index(drop=True)

pullm_tomek_train_set = pullm_training_set.drop(pullm_tomek_train_index)
pullm_tomek_train_set.to_csv('Z:\\Nathan\\Models\\student_risk\\outliers\\pullm_frst_tomek_training_set.csv', encoding='utf-8', index=False)
pullm_tomek_valid_set = pullm_validation_set.drop(pullm_tomek_valid_index)
pullm_tomek_valid_set.to_csv('Z:\\Nathan\\Models\\student_risk\\outliers\\pullm_frst_tomek_validation_set.csv', encoding='utf-8', index=False)

#%%
# Vancouver undersample
vanco_x_train = vanco_training_set.drop(columns=['enrl_ind','emplid'])
vanco_x_cv = vanco_validation_set.drop(columns=['enrl_ind','emplid'])

vanco_x_test = vanco_testing_set[vanco_x_vars]

vanco_y_train = vanco_training_set['enrl_ind']
vanco_y_cv = vanco_validation_set['enrl_ind']
# vanco_y_test = vanco_testing_set['enrl_ind']

vanco_tomek_prep = make_column_transformer(
	# (StandardScaler(), [
	# 					'distance',
	# 					# 'age',
	# 					# 'min_week_from_term_begin_dt',
	# 					# 'max_week_from_term_begin_dt',
	# 					'count_week_from_term_begin_dt',
	# 					# 'sat_erws',
	# 					# 'sat_mss',
	# 					# 'sat_comp',
	# 					# 'attendee_total_visits',
	# 					'pop_dens', 
	# 					# 'qvalue', 
	# 					# 'gini_indx',
	# 					'median_inc',
	# 					# 'pvrt_rate',
	# 					'median_value',
	# 					# 'educ_rate',
	# 					# 'pct_blk',
	# 					# 'pct_ai',
	# 					# 'pct_asn',
	# 					# 'pct_hawi',
	# 					# 'pct_oth',
	# 					# 'pct_two',
	# 					# 'pct_non',
	# 					# 'pct_hisp',
	# 					# 'term_credit_hours',
	# 					'high_school_gpa',
	# 					# 'awe_instrument',
	# 					# 'cdi_instrument',
	# 					'fall_avg_difficulty',
	# 					# 'fall_avg_pct_withdrawn',
	# 					# 'fall_avg_pct_CDFW',
	# 					# 'fall_avg_pct_CDF',
	# 					'fall_lec_count',
	# 					'fall_lab_count',
	# 					# 'fall_int_count',
	# 					# 'fall_stu_count',
	# 					# 'fall_sem_count',
	# 					# 'fall_oth_count',
	# 					'fall_lec_contact_hrs',
	# 					'fall_lab_contact_hrs',
	# 					# 'fall_int_contact_hrs',
	# 					# 'fall_stu_contact_hrs',
	# 					# 'fall_sem_contact_hrs',
	# 					# 'fall_oth_contact_hrs',
	# 					# 'total_fall_contact_hrs',
	# 					'total_fall_units',
	# 					'fall_withdrawn_hours',
	# 					'cum_adj_transfer_hours',
	# 					# 'term_credit_hours',
	# 					# 'fed_efc',
	# 					# 'fed_need', 
	# 					'unmet_need_ofr'
	# 					]),
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
vanco_x_cv = vanco_tomek_prep.transform(vanco_x_cv)
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

vanco_under_train = TomekLinks(sampling_strategy='all', n_jobs=-1)
vanco_under_valid = TomekLinks(sampling_strategy='all', n_jobs=-1)

vanco_x_train, vanco_y_train = vanco_under_train.fit_resample(vanco_x_train, vanco_y_train)
vanco_x_cv, vanco_y_cv = vanco_under_valid.fit_resample(vanco_x_cv, vanco_y_cv)

vanco_tomek_train_index = vanco_under_train.sample_indices_
vanco_tomek_valid_index = vanco_under_valid.sample_indices_
vanco_training_set = vanco_training_set.reset_index(drop=True)
vanco_validation_set = vanco_validation_set.reset_index(drop=True)

vanco_tomek_train_set = vanco_training_set.drop(vanco_tomek_train_index)
vanco_tomek_train_set.to_csv('Z:\\Nathan\\Models\\student_risk\\outliers\\vanco_frst_tomek_training_set.csv', encoding='utf-8', index=False)
vanco_tomek_valid_set = vanco_validation_set.drop(vanco_tomek_valid_index)
vanco_tomek_valid_set.to_csv('Z:\\Nathan\\Models\\student_risk\\outliers\\vanco_frst_tomek_validation_set.csv', encoding='utf-8', index=False)

#%%
# Tri-Cities undersample
trici_x_train = trici_training_set.drop(columns=['enrl_ind','emplid'])
trici_x_cv = trici_validation_set.drop(columns=['enrl_ind','emplid'])

trici_x_test = trici_testing_set[trici_x_vars]

trici_y_train = trici_training_set['enrl_ind']
trici_y_cv = trici_validation_set['enrl_ind']
# trici_y_test = trici_testing_set['enrl_ind']

trici_tomek_prep = make_column_transformer(
	# (StandardScaler(), [
	# 					'distance',
	# 					# 'age',
	# 					# 'min_week_from_term_begin_dt',
	# 					# 'max_week_from_term_begin_dt',
	# 					'count_week_from_term_begin_dt',
	# 					# 'sat_erws',
	# 					# 'sat_mss',
	# 					# 'sat_comp',
	# 					# 'attendee_total_visits',
	# 					'pop_dens', 
	# 					# 'qvalue', 
	# 					# 'gini_indx',
	# 					'median_inc',
	# 					# 'pvrt_rate',
	# 					'median_value',
	# 					# 'educ_rate',
	# 					# 'pct_blk',
	# 					# 'pct_ai',
	# 					# 'pct_asn',
	# 					# 'pct_hawi',
	# 					# 'pct_oth',
	# 					# 'pct_two',
	# 					# 'pct_non',
	# 					# 'pct_hisp',
	# 					# 'term_credit_hours',
	# 					'high_school_gpa',
	# 					# 'awe_instrument',
	# 					# 'cdi_instrument',
	# 					'fall_avg_difficulty',
	# 					# 'fall_avg_pct_withdrawn',
	# 					# 'fall_avg_pct_CDFW',
	# 					# 'fall_avg_pct_CDF',
	# 					'fall_lec_count',
	# 					'fall_lab_count',
	# 					# 'fall_int_count',
	# 					# 'fall_stu_count',
	# 					# 'fall_sem_count',
	# 					# 'fall_oth_count',
	# 					'fall_lec_contact_hrs',
	# 					'fall_lab_contact_hrs',
	# 					# 'fall_int_contact_hrs',
	# 					# 'fall_stu_contact_hrs',
	# 					# 'fall_sem_contact_hrs',
	# 					# 'fall_oth_contact_hrs',
	# 					# 'total_fall_contact_hrs',
	# 					'total_fall_units',
	# 					'fall_withdrawn_hours',
	# 					'cum_adj_transfer_hours',
	# 					# 'term_credit_hours',
	# 					# 'fed_efc',
	# 					# 'fed_need', 
	# 					'unmet_need_ofr'
	# 					]),
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
trici_x_cv = trici_tomek_prep.transform(trici_x_cv)
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

trici_under_train = TomekLinks(sampling_strategy='all', n_jobs=-1)
trici_under_valid = TomekLinks(sampling_strategy='all', n_jobs=-1)

trici_x_train, trici_y_train = trici_under_train.fit_resample(trici_x_train, trici_y_train)
trici_x_cv, trici_y_cv = trici_under_valid.fit_resample(trici_x_cv, trici_y_cv)

trici_tomek_train_index = trici_under_train.sample_indices_
trici_tomek_valid_index = trici_under_valid.sample_indices_
trici_training_set = trici_training_set.reset_index(drop=True)
trici_validation_set = trici_validation_set.reset_index(drop=True)

trici_tomek_train_set = trici_training_set.drop(trici_tomek_train_index)
trici_tomek_train_set.to_csv('Z:\\Nathan\\Models\\student_risk\\outliers\\trici_frst_tomek_training_set.csv', encoding='utf-8', index=False)
trici_tomek_valid_set = trici_validation_set.drop(trici_tomek_valid_index)
trici_tomek_valid_set.to_csv('Z:\\Nathan\\Models\\student_risk\\outliers\\trici_frst_tomek_validation_set.csv', encoding='utf-8', index=False)

#%%
# University undersample
univr_x_train = univr_training_set.drop(columns=['enrl_ind','emplid'])
univr_x_cv = univr_validation_set.drop(columns=['enrl_ind','emplid'])

univr_x_test = univr_testing_set[univr_x_vars]

univr_y_train = univr_training_set['enrl_ind']
univr_y_cv = univr_validation_set['enrl_ind']
# univr_y_test = univr_testing_set['enrl_ind']

univr_tomek_prep = make_column_transformer(
	# (StandardScaler(), [
	# 					'distance',
	# 					# 'age',
	# 					# 'min_week_from_term_begin_dt',
	# 					# 'max_week_from_term_begin_dt',
	# 					'count_week_from_term_begin_dt',
	# 					# 'sat_erws',
	# 					# 'sat_mss',
	# 					# 'sat_comp',
	# 					# 'attendee_total_visits',
	# 					'pop_dens', 
	# 					# 'qvalue', 
	# 					# 'gini_indx',
	# 					'median_inc',
	# 					# 'pvrt_rate',
	# 					'median_value',
	# 					# 'educ_rate',
	# 					# 'pct_blk',
	# 					# 'pct_ai',
	# 					# 'pct_asn',
	# 					# 'pct_hawi',
	# 					# 'pct_oth',
	# 					# 'pct_two',
	# 					# 'pct_non',
	# 					# 'pct_hisp',
	# 					# 'term_credit_hours',
	# 					'high_school_gpa',
	# 					# 'awe_instrument',
	# 					# 'cdi_instrument',
	# 					'fall_avg_difficulty',
	# 					# 'fall_avg_pct_withdrawn',
	# 					# 'fall_avg_pct_CDFW',
	# 					# 'fall_avg_pct_CDF',
	# 					'fall_lec_count',
	# 					'fall_lab_count',
	# 					# 'fall_int_count',
	# 					# 'fall_stu_count',
	# 					# 'fall_sem_count',
	# 					# 'fall_oth_count',
	# 					'fall_lec_contact_hrs',
	# 					'fall_lab_contact_hrs',
	# 					# 'fall_int_contact_hrs',
	# 					# 'fall_stu_contact_hrs',
	# 					# 'fall_sem_contact_hrs',
	# 					# 'fall_oth_contact_hrs',
	# 					# 'total_fall_contact_hrs',
	# 					'total_fall_units',
	# 					'fall_withdrawn_hours',
	# 					'cum_adj_transfer_hours',
	# 					# 'term_credit_hours',
	# 					# 'fed_efc',
	# 					# 'fed_need', 
	# 					'unmet_need_ofr'
	# 					]),
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
univr_x_cv = univr_tomek_prep.transform(univr_x_cv)
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

univr_under_train = TomekLinks(sampling_strategy='all', n_jobs=-1)
univr_under_valid = TomekLinks(sampling_strategy='all', n_jobs=-1)

univr_x_train, univr_y_train = univr_under_train.fit_resample(univr_x_train, univr_y_train)
univr_x_cv, univr_y_cv = univr_under_valid.fit_resample(univr_x_cv, univr_y_cv)

univr_tomek_train_index = univr_under_train.sample_indices_
univr_tomek_valid_index = univr_under_valid.sample_indices_
univr_training_set = univr_training_set.reset_index(drop=True)
univr_validation_set = univr_validation_set.reset_index(drop=True)

univr_tomek_train_set = univr_training_set.drop(univr_tomek_train_index)
univr_tomek_train_set.to_csv('Z:\\Nathan\\Models\\student_risk\\outliers\\univr_frst_tomek_training_set.csv', encoding='utf-8', index=False)
univr_tomek_valid_set = univr_validation_set.drop(univr_tomek_valid_index)
univr_tomek_valid_set.to_csv('Z:\\Nathan\\Models\\student_risk\\outliers\\univr_frst_tomek_validation_set.csv', encoding='utf-8', index=False)

#%%
# Standard logistic model

# Pullman standard model
print('\nStandard logistic model for Pullman freshmen...\n')

try:
	pullm_y, pullm_x = dmatrices('enrl_ind ~ ' + ' + '.join(pullm_x_vars), data=pullm_logit_df, return_type='dataframe')

	pullm_logit_mod = Logit(pullm_y, pullm_x)
	pullm_logit_res = pullm_logit_mod.fit(maxiter=500)
	print(pullm_logit_res.summary())

	# Pullman VIF
	print('\nVIF for Pullman...\n')
	pullm_vif = pd.DataFrame()
	pullm_vif['vif factor'] = [variance_inflation_factor(pullm_x.values, i) for i in range(pullm_x.shape[1])]
	pullm_vif['features'] = pullm_x.columns
	pullm_vif.sort_values(by=['vif factor'], ascending=False, inplace=True, ignore_index=True)
	print(pullm_vif.round(1).to_string())
	print('\n')
	
except:
	print('Failed to converge or model misspecification: Linear combination, singular matrix, divide by zero, or separation\n')

print('\n')

#%%
# Vancouver standard model
print('\nStandard logistic model for Vancouver freshmen...\n')

try:
	vanco_y, vanco_x = dmatrices('enrl_ind ~ ' + ' + '.join(vanco_x_vars), data=vanco_logit_df, return_type='dataframe')

	vanco_logit_mod = Logit(vanco_y, vanco_x)
	vanco_logit_res = vanco_logit_mod.fit(maxiter=500)
	print(vanco_logit_res.summary())

	# Vancouver VIF
	print('\nVIF for Vancouver...\n')
	vanco_vif = pd.DataFrame()
	vanco_vif['vif factor'] = [variance_inflation_factor(vanco_x.values, i) for i in range(vanco_x.shape[1])]
	vanco_vif['features'] = vanco_x.columns
	vanco_vif.sort_values(by=['vif factor'], ascending=False, inplace=True, ignore_index=True)
	print(vanco_vif.round(1).to_string())
	print('\n')

except:
	print('\nFailed to converge or model misspecification: Linear combination, singular matrix, divide by zero, or separation')

print('\n')

#%%
# Tri-Cities standard model
print('\nStandard logistic model for Tri-Cities freshmen...\n')

try:
	trici_y, trici_x = dmatrices('enrl_ind ~ ' + ' + '.join(trici_x_vars), data=trici_logit_df, return_type='dataframe')

	trici_logit_mod = Logit(trici_y, trici_x)
	trici_logit_res = trici_logit_mod.fit(maxiter=500)
	print(trici_logit_res.summary())

	# Tri-Cities VIF
	print('\nVIF for Tri-Cities...\n')
	trici_vif = pd.DataFrame()
	trici_vif['vif factor'] = [variance_inflation_factor(trici_x.values, i) for i in range(trici_x.shape[1])]
	trici_vif['features'] = trici_x.columns
	trici_vif.sort_values(by=['vif factor'], ascending=False, inplace=True, ignore_index=True)
	print(trici_vif.round(1).to_string())
	print('\n')
	
except:
	print('Failed to converge or model misspecification: Linear combination, singular matrix, divide by zero, or separation\n')

print('\n')

#%%
# University standard model
print('\nStandard logistic model for University freshmen...\n')

try:
	univr_y, univr_x = dmatrices('enrl_ind ~ ' + ' + '.join(univr_x_vars), data=univr_logit_df, return_type='dataframe')

	univr_logit_mod = Logit(univr_y, univr_x)
	univr_logit_res = univr_logit_mod.fit(maxiter=500)
	print(univr_logit_res.summary())

	# University VIF
	print('\nVIF for University...\n')
	univr_vif = pd.DataFrame()
	univr_vif['vif factor'] = [variance_inflation_factor(univr_x.values, i) for i in range(univr_x.shape[1])]
	univr_vif['features'] = univr_x.columns
	univr_vif.sort_values(by=['vif factor'], ascending=False, inplace=True, ignore_index=True)
	print(univr_vif.round(1).to_string())
	print('\n')

except:
	print('Failed to converge or model misspecification: Linear combination, singular matrix, divide by zero, or separation\n')

print('\n')

#%%
print('Run machine learning models for freshmen...\n')

# Logistic model

# Pullman logistic
# pullm_lreg = LogisticRegression(penalty='elasticnet', class_weight='balanced', solver='saga', max_iter=5000, l1_ratio=0.0, C=1.0, n_jobs=-1, verbose=False).fit(pullm_x_train, pullm_y_train)

# pullm_lreg_probs = pullm_lreg.predict_proba(pullm_x_train)
# pullm_lreg_probs = pullm_lreg_probs[:, 1]
# pullm_lreg_auc = roc_auc_score(pullm_y_train, pullm_lreg_probs)

# print(f'Overall accuracy for Pullman logistic model (training): {pullm_lreg.score(pullm_x_train, pullm_y_train):.4f}')
# print(f'ROC AUC for Pullman logistic model (training): {pullm_lreg_auc:.4f}')
# print(f'Overall accuracy for Pullman logistic model (validation): {pullm_lreg.score(pullm_x_cv, pullm_y_cv):.4f}\n')

#%%
# Vancouver logistic
# vanco_lreg = LogisticRegression(penalty='elasticnet', class_weight='balanced', solver='saga', max_iter=5000, l1_ratio=0.0, C=1.0, n_jobs=-1, verbose=False).fit(vanco_x_train, vanco_y_train)

# vanco_lreg_probs = vanco_lreg.predict_proba(vanco_x_train)
# vanco_lreg_probs = vanco_lreg_probs[:, 1]
# vanco_lreg_auc = roc_auc_score(vanco_y_train, vanco_lreg_probs)

# print(f'Overall accuracy for Vancouver logistic model (training): {vanco_lreg.score(vanco_x_train, vanco_y_train):.4f}')
# print(f'ROC AUC for Vancouver logistic model (training): {vanco_lreg_auc:.4f}')
# print(f'Overall accuracy for Vancouver logistic model (validation): {vanco_lreg.score(vanco_x_cv, vanco_y_cv):.4f}\n')

#%%
# Tri-Cities logistic
# trici_lreg = LogisticRegression(penalty='elasticnet', class_weight='balanced', solver='saga', max_iter=5000, l1_ratio=0.0, C=1.0, n_jobs=-1, verbose=False).fit(trici_x_train, trici_y_train)

# trici_lreg_probs = trici_lreg.predict_proba(trici_x_train)
# trici_lreg_probs = trici_lreg_probs[:, 1]
# trici_lreg_auc = roc_auc_score(trici_y_train, trici_lreg_probs)

# print(f'Overall accuracy for Tri-Cities logistic model (training): {trici_lreg.score(trici_x_train, trici_y_train):.4f}')
# print(f'ROC AUC for Tri-Cities logistic model (training): {trici_lreg_auc:.4f}')
# print(f'Overall accuracy for Tri-Cities logistic model (validation): {trici_lreg.score(trici_x_cv, trici_y_cv):.4f}\n')

#%%
# University logistic
# univr_lreg = LogisticRegression(penalty='elasticnet', class_weight='balanced', solver='saga', max_iter=5000, l1_ratio=0.0, C=1.0, n_jobs=-1, verbose=False).fit(univr_x_train, univr_y_train)

# univr_lreg_probs = univr_lreg.predict_proba(univr_x_train)
# univr_lreg_probs = univr_lreg_probs[:, 1]
# univr_lreg_auc = roc_auc_score(univr_y_train, univr_lreg_probs)

# print(f'Overall accuracy for University logistic model (training): {univr_lreg.score(univr_x_train, univr_y_train):.4f}')
# print(f'ROC AUC for University logistic model (training): {univr_lreg_auc:.4f}')
# print(f'Overall accuracy for University logistic model (validation): {univr_lreg.score(univr_x_cv, univr_y_cv):.4f}\n')

#%%
# Stochastic gradient descent model

# Pullman SGD
# pullm_sgd = SGDClassifier(loss='modified_huber', penalty='elasticnet', class_weight='balanced', early_stopping=False, max_iter=5000, l1_ratio=0.0, learning_rate='adaptive', eta0=0.0001, tol=0.0001, n_iter_no_change=100, n_jobs=-1, verbose=False).fit(pullm_x_train, pullm_y_train)

# pullm_sgd_probs = pullm_sgd.predict_proba(pullm_x_train)
# pullm_sgd_probs = pullm_sgd_probs[:, 1]
# pullm_sgd_auc = roc_auc_score(pullm_y_train, pullm_sgd_probs)

# print(f'Overall accuracy for Pullman SGD model (training): {pullm_sgd.score(pullm_x_train, pullm_y_train):.4f}')
# print(f'ROC AUC for Pullman SGD model (training): {pullm_sgd_auc:.4f}')
# print(f'Overall accuracy for Pullman SGD model (validation): {pullm_sgd.score(pullm_x_cv, pullm_y_cv):.4f}\n')

#%%
# Vancouver SGD
# vanco_sgd = SGDClassifier(loss='modified_huber', penalty='elasticnet', class_weight='balanced', early_stopping=False, max_iter=5000, l1_ratio=0.0, learning_rate='adaptive', eta0=0.0001, tol=0.0001, n_iter_no_change=100, n_jobs=-1, verbose=False).fit(vanco_x_train, vanco_y_train)

# vanco_sgd_probs = vanco_sgd.predict_proba(vanco_x_train)
# vanco_sgd_probs = vanco_sgd_probs[:, 1]
# vanco_sgd_auc = roc_auc_score(vanco_y_train, vanco_sgd_probs)

# print(f'Overall accuracy for Vancouver SGD model (training): {vanco_sgd.score(vanco_x_train, vanco_y_train):.4f}')
# print(f'ROC AUC for Vancouver SGD model (training): {vanco_sgd_auc:.4f}')
# print(f'Overall accuracy for Vancouver SGD model (validation): {vanco_sgd.score(vanco_x_cv, vanco_y_cv):.4f}\n')

#%%
# Tri-Cities SGD
# trici_sgd = SGDClassifier(loss='modified_huber', penalty='elasticnet', class_weight='balanced', early_stopping=False, max_iter=5000, l1_ratio=0.0, learning_rate='adaptive', eta0=0.0001, tol=0.0001, n_iter_no_change=100, n_jobs=-1, verbose=False).fit(trici_x_train, trici_y_train)

# trici_sgd_probs = trici_sgd.predict_proba(trici_x_train)
# trici_sgd_probs = trici_sgd_probs[:, 1]
# trici_sgd_auc = roc_auc_score(trici_y_train, trici_sgd_probs)

# print(f'Overall accuracy for Tri-Cities SGD model (training): {trici_sgd.score(trici_x_train, trici_y_train):.4f}')
# print(f'ROC AUC for Tri-Cities SGD model (training): {trici_sgd_auc:.4f}')
# print(f'Overall accuracy for Tri-Cities SGD model (validation): {trici_sgd.score(trici_x_cv, trici_y_cv):.4f}\n')

#%%
# University SGD
# univr_sgd = SGDClassifier(loss='modified_huber', penalty='elasticnet', class_weight='balanced', early_stopping=False, max_iter=5000, l1_ratio=0.0, learning_rate='adaptive', eta0=0.0001, tol=0.0001, n_iter_no_change=100, n_jobs=-1, verbose=False).fit(univr_x_train, univr_y_train)

# univr_sgd_probs = univr_sgd.predict_proba(univr_x_train)
# univr_sgd_probs = univr_sgd_probs[:, 1]
# univr_sgd_auc = roc_auc_score(univr_y_train, univr_sgd_probs)

# print(f'Overall accuracy for University SGD model (training): {univr_sgd.score(univr_x_train, univr_y_train):.4f}')
# print(f'ROC AUC for University SGD model (training): {univr_sgd_auc:.4f}')
# print(f'Overall accuracy for University SGD model (validation): {univr_sgd.score(univr_x_cv, univr_y_cv):.4f}\n')

#%%
# Multi-layer perceptron model

# Pullman MLP
# pullm_mlp = MLPClassifier(hidden_layer_sizes=(75,50,25), activation='relu', solver='sgd', alpha=2.5, learning_rate_init=0.001, n_iter_no_change=25, max_iter=5000, verbose=False).fit(pullm_x_train, pullm_y_train)

# pullm_mlp_probs = pullm_mlp.predict_proba(pullm_x_train)
# pullm_mlp_probs = pullm_mlp_probs[:, 1]
# pullm_mlp_auc = roc_auc_score(pullm_y_train, pullm_mlp_probs)

# print(f'\nOverall accuracy for multi-layer perceptron model (training): {pullm_mlp.score(pullm_x_train, pullm_y_train):.4f}')
# print(f'ROC AUC for multi-layer perceptron model (training): {pullm_mlp_auc:.4f}\n')

#%%
# Vancouver MLP
# vanco_mlp = MLPClassifier(hidden_layer_sizes=(75,50,25), activation='relu', solver='sgd', alpha=2.5, learning_rate_init=0.001, n_iter_no_change=25, max_iter=5000, verbose=False).fit(vanco_x_train, vanco_y_train)

# vanco_mlp_probs = vanco_mlp.predict_proba(vanco_x_train)
# vanco_mlp_probs = vanco_mlp_probs[:, 1]
# vanco_mlp_auc = roc_auc_score(vanco_y_train, vanco_mlp_probs)

# print(f'\nOverall accuracy for multi-layer perceptron model (training): {vanco_mlp.score(vanco_x_train, vanco_y_train):.4f}')
# print(f'ROC AUC for multi-layer perceptron model (training): {vanco_mlp_auc:.4f}\n')

#%%
# Tri-Cities MLP
# trici_mlp = MLPClassifier(hidden_layer_sizes=(75,50,25), activation='relu', solver='sgd', alpha=2.5, learning_rate_init=0.001, n_iter_no_change=25, max_iter=5000, verbose=False).fit(trici_x_train, trici_y_train)

# trici_mlp_probs = trici_mlp.predict_proba(trici_x_train)
# trici_mlp_probs = trici_mlp_probs[:, 1]
# trici_mlp_auc = roc_auc_score(trici_y_train, trici_mlp_probs)

# print(f'\nOverall accuracy for multi-layer perceptron model (training): {trici_mlp.score(trici_x_train, trici_y_train):.4f}')
# print(f'ROC AUC for multi-layer perceptron model (training): {trici_mlp_auc:.4f}\n')

#%%
# University MLP
# univr_mlp = MLPClassifier(hidden_layer_sizes=(75,50,25), activation='relu', solver='sgd', alpha=2.5, learning_rate_init=0.001, n_iter_no_change=25, max_iter=5000, verbose=False).fit(univr_x_train, univr_y_train)

# univr_mlp_probs = univr_mlp.predict_proba(univr_x_train)
# univr_mlp_probs = univr_mlp_probs[:, 1]
# univr_mlp_auc = roc_auc_score(univr_y_train, univr_mlp_probs)

# print(f'\nOverall accuracy for University multi-layer perceptron model (training): {univr_mlp.score(univr_x_train, univr_y_train):.4f}')
# print(f'ROC AUC for University multi-layer perceptron model (training): {univr_mlp_auc:.4f}\n')

#%%
# XGBoost model

# Pullman XGBoost tuning
# pullm_class_weight = pullm_y_train[pullm_y_train == 0].count() / pullm_y_train[pullm_y_train == 1].count()
# pullm_hyperparameters = [{'max_depth': np.linspace(1, 10, 10, dtype=int, endpoint=True),
# 						'gamma': np.linspace(1, 10, 10, dtype=int, endpoint=True),
# 						'learning_rate': [0.01, 0.5, 1.0]}]

# pullm_gridsearch = HalvingGridSearchCV(XGBClassifier(tree_method='hist', grow_policy='depthwise', scale_pos_weight=pullm_class_weight, eval_metric='logloss', use_label_encoder=False, n_jobs=-1), pullm_hyperparameters, resource='n_estimators', factor=3, min_resources=2, max_resources=500, scoring='roc_auc', cv=5, aggressive_elimination=True, verbose=verbose, n_jobs=-1)
# pullm_best_model = pullm_gridsearch.fit(pullm_x_train, pullm_y_train)

# print(f'Best Pullman XGB parameters: {pullm_gridsearch.best_params_}')

#%%
# Pullman XGBoost
# pullm_class_weight = pullm_y_train[pullm_y_train == 0].count() / pullm_y_train[pullm_y_train == 1].count()
# pullm_xgb = XGBClassifier(tree_method='hist', grow_policy='depthwise', scale_pos_weight=pullm_class_weight, 
# 								eval_metric='logloss', **pullm_gridsearch.best_params_, use_label_encoder=False, n_jobs=-1).fit(pullm_x_train, pullm_y_train, eval_set=[(pullm_x_cv, pullm_y_cv)], early_stopping_rounds=20, verbose=False)

# pullm_xgb_probs = pullm_xgb.predict_proba(pullm_x_train)
# pullm_xgb_probs = pullm_xgb_probs[:, 1]
# pullm_xgb_auc = roc_auc_score(pullm_y_train, pullm_xgb_probs)

# print(f'Overall accuracy for Pullman XGB model (training): {pullm_xgb.score(pullm_x_train, pullm_y_train):.4f}')
# print(f'ROC AUC for Pullman XGB model (training): {pullm_xgb_auc:.4f}')
# print(f'Overall accuracy for Pullman XGB model (validation): {pullm_xgb.score(pullm_x_cv, pullm_y_cv):.4f}\n')

#%%
# Vancouver XGBoost tuning
# vanco_class_weight = vanco_y_train[vanco_y_train == 0].count() / vanco_y_train[vanco_y_train == 1].count()
# vanco_hyperparameters = [{'max_depth': np.linspace(1, 10, 10, dtype=int, endpoint=True),
# 						'gamma': np.linspace(1, 10, 10, dtype=int, endpoint=True),
# 						'learning_rate': [0.01, 0.5, 1.0]}]

# vanco_gridsearch = HalvingGridSearchCV(XGBClassifier(tree_method='hist', grow_policy='depthwise', scale_pos_weight=vanco_class_weight, eval_metric='logloss', use_label_encoder=False, n_jobs=-1), vanco_hyperparameters, resource='n_estimators', factor=3, min_resources=2, max_resources=500, scoring='roc_auc', cv=5, aggressive_elimination=True, verbose=verbose, n_jobs=-1)
# vanco_best_model = vanco_gridsearch.fit(vanco_x_train, vanco_y_train)

# print(f'Best Vancouver XGB parameters: {vanco_gridsearch.best_params_}')

#%%
# Vancouver XGBoost
# vanco_class_weight = vanco_y_train[vanco_y_train == 0].count() / vanco_y_train[vanco_y_train == 1].count()
# vanco_xgb = XGBClassifier(tree_method='hist', grow_policy='depthwise', scale_pos_weight=vanco_class_weight, 
# 								eval_metric='logloss', **vanco_gridsearch.best_params_, use_label_encoder=False, n_jobs=-1).fit(vanco_x_train, vanco_y_train, eval_set=[(vanco_x_cv, vanco_y_cv)], early_stopping_rounds=20, verbose=False)

# vanco_xgb_probs = vanco_xgb.predict_proba(vanco_x_train)
# vanco_xgb_probs = vanco_xgb_probs[:, 1]
# vanco_xgb_auc = roc_auc_score(vanco_y_train, vanco_xgb_probs)

# print(f'Overall accuracy for Vancouver XGB model (training): {vanco_xgb.score(vanco_x_train, vanco_y_train):.4f}')
# print(f'ROC AUC for Vancouver XGB model (training): {vanco_xgb_auc:.4f}')
# print(f'Overall accuracy for Vancouver XGB model (validation): {vanco_xgb.score(vanco_x_cv, vanco_y_cv):.4f}\n')

#%%
# Tri-Cities XGBoost tuning
# trici_class_weight = trici_y_train[trici_y_train == 0].count() / trici_y_train[trici_y_train == 1].count()
# trici_hyperparameters = [{'max_depth': np.linspace(1, 10, 10, dtype=int, endpoint=True),
# 						'gamma': np.linspace(1, 10, 10, dtype=int, endpoint=True),
# 						'learning_rate': [0.01, 0.5, 1.0]}]

# trici_gridsearch = HalvingGridSearchCV(XGBClassifier(tree_method='hist', grow_policy='depthwise', scale_pos_weight=trici_class_weight, eval_metric='logloss', use_label_encoder=False, n_jobs=-1), trici_hyperparameters, resource='n_estimators', factor=3, min_resources=2, max_resources=500, scoring='roc_auc', cv=5, aggressive_elimination=True, verbose=verbose, n_jobs=-1)
# trici_best_model = trici_gridsearch.fit(trici_x_train, trici_y_train)

# print(f'Best Tri-Cities XGB parameters: {trici_gridsearch.best_params_}')

#%%
# Tri-Cities XGBoost
# trici_class_weight = trici_y_train[trici_y_train == 0].count() / trici_y_train[trici_y_train == 1].count()
# trici_xgb = XGBClassifier(tree_method='hist', grow_policy='depthwise', scale_pos_weight=trici_class_weight, 
# 								eval_metric='logloss', **trici_gridsearch.best_params_, use_label_encoder=False, n_jobs=-1).fit(trici_x_train, trici_y_train, eval_set=[(trici_x_cv, trici_y_cv)], early_stopping_rounds=20, verbose=False)

# trici_xgb_probs = trici_xgb.predict_proba(trici_x_train)
# trici_xgb_probs = trici_xgb_probs[:, 1]
# trici_xgb_auc = roc_auc_score(trici_y_train, trici_xgb_probs)

# print(f'Overall accuracy for Tri-Cities XGB model (training): {trici_xgb.score(trici_x_train, trici_y_train):.4f}')
# print(f'ROC AUC for Tri-Cities XGB model (training): {trici_xgb_auc:.4f}')
# print(f'Overall accuracy for Tri-Cities XGB model (validation): {trici_xgb.score(trici_x_cv, trici_y_cv):.4f}\n')

#%%
# University XGBoost tuning
# univr_class_weight = univr_y_train[univr_y_train == 0].count() / univr_y_train[univr_y_train == 1].count()
# univr_hyperparameters = [{'max_depth': np.linspace(1, 10, 10, dtype=int, endpoint=True),
# 						'gamma': np.linspace(1, 10, 10, dtype=int, endpoint=True),
# 						'learning_rate': [0.01, 0.5, 1.0]}]

# univr_gridsearch = HalvingGridSearchCV(XGBClassifier(tree_method='hist', grow_policy='depthwise', scale_pos_weight=univr_class_weight, eval_metric='logloss', use_label_encoder=False, n_jobs=-1), univr_hyperparameters, resource='n_estimators', factor=3, min_resources=2, max_resources=500, scoring='roc_auc', cv=5, aggressive_elimination=True, verbose=verbose, n_jobs=-1)
# univr_best_model = univr_gridsearch.fit(univr_x_train, univr_y_train)

# print(f'Best University XGB parameters: {univr_gridsearch.best_params_}')

#%%
# University XGBboost
# univr_class_weight = univr_y_train[univr_y_train == 0].count() / univr_y_train[univr_y_train == 1].count()
# univr_xgb = XGBClassifier(tree_method='hist', grow_policy='depthwise', scale_pos_weight=univr_class_weight, 
# 								eval_metric='logloss', **univr_gridsearch.best_params_, use_label_encoder=False, n_jobs=-1).fit(univr_x_train, univr_y_train, eval_set=[(univr_x_cv, univr_y_cv)], early_stopping_rounds=20, verbose=False)

# univr_xgb_probs = univr_xgb.predict_proba(univr_x_train)
# univr_xgb_probs = univr_xgb_probs[:, 1]
# univr_xgb_auc = roc_auc_score(univr_y_train, univr_xgb_probs)

# print(f'Overall accuracy for University XGB model (training): {univr_xgb.score(univr_x_train, univr_y_train):.4f}')
# print(f'ROC AUC for University XGB model (training): {univr_xgb_auc:.4f}')
# print(f'Overall accuracy for University XGB model (validation): {univr_xgb.score(univr_x_cv, univr_y_cv):.4f}\n')

#%%
# Pullman Random Forest tuning
# pullm_class_weight = pullm_y_train[pullm_y_train == 0].count() / pullm_y_train[pullm_y_train == 1].count()
# pullm_hyperparameters = [{'max_depth': np.linspace(1, 10, 10, dtype=int, endpoint=True),
# 						'gamma': np.linspace(1, 10, 10, dtype=int, endpoint=True)}]

# pullm_gridsearch = HalvingGridSearchCV(XGBRFClassifier(tree_method='hist', grow_policy='depthwise', subsample=0.8, colsample_bytree=0.8, scale_pos_weight=pullm_class_weight, eval_metric='logloss', use_label_encoder=False, n_jobs=-1), pullm_hyperparameters, resource='n_estimators', factor=3, min_resources=2, max_resources=500, scoring='roc_auc', cv=5, aggressive_elimination=True, verbose=verbose, n_jobs=-1)
# pullm_best_model = pullm_gridsearch.fit(pullm_x_train, pullm_y_train)

# print(f'Best Pullman Random Forest parameters: {pullm_gridsearch.best_params_}')

#%%
# Pullman Random Forest
# pullm_class_weight = pullm_y_train[pullm_y_train == 0].count() / pullm_y_train[pullm_y_train == 1].count()
# pullm_rf = XGBRFClassifier(tree_method='hist', grow_policy='depthwise', subsample=0.8, colsample_bytree=0.8, scale_pos_weight=pullm_class_weight, 
# 								eval_metric='logloss', **pullm_gridsearch.best_params_, use_label_encoder=False, n_jobs=-1).fit(pullm_x_train, pullm_y_train, verbose=False)

# pullm_rf_probs = pullm_rf.predict_proba(pullm_x_train)
# pullm_rf_probs = pullm_rf_probs[:, 1]
# pullm_rf_auc = roc_auc_score(pullm_y_train, pullm_rf_probs)

# print(f'Overall accuracy for Pullman Random Forest model (training): {pullm_rf.score(pullm_x_train, pullm_y_train):.4f}')
# print(f'ROC AUC for Pullman Random Forest model (training): {pullm_rf_auc:.4f}')
# print(f'Overall accuracy for Pullman Random Forest model (validation): {pullm_rf.score(pullm_x_cv, pullm_y_cv):.4f}\n')

#%%
# Vancouver Random Forest tuning
# vanco_class_weight = vanco_y_train[vanco_y_train == 0].count() / vanco_y_train[vanco_y_train == 1].count()
# vanco_hyperparameters = [{'max_depth': np.linspace(1, 10, 10, dtype=int, endpoint=True),
# 						'gamma': np.linspace(1, 10, 10, dtype=int, endpoint=True)}]

# vanco_gridsearch = HalvingGridSearchCV(XGBRFClassifier(tree_method='hist', grow_policy='depthwise', subsample=0.8, colsample_bytree=0.8, scale_pos_weight=vanco_class_weight, eval_metric='logloss', use_label_encoder=False, n_jobs=-1), vanco_hyperparameters, resource='n_estimators', factor=3, min_resources=2, max_resources=500, scoring='roc_auc', cv=5, aggressive_elimination=True, verbose=verbose, n_jobs=-1)
# vanco_best_model = vanco_gridsearch.fit(vanco_x_train, vanco_y_train)

# print(f'Best Vancouver Random Forest parameters: {vanco_gridsearch.best_params_}')

#%%
# Vancouver Random Forest
# vanco_class_weight = vanco_y_train[vanco_y_train == 0].count() / vanco_y_train[vanco_y_train == 1].count()
# vanco_rf = XGBRFClassifier(tree_method='hist', grow_policy='depthwise', subsample=0.8, colsample_bytree=0.8, scale_pos_weight=vanco_class_weight, 
# 								eval_metric='logloss', **vanco_gridsearch.best_params_, use_label_encoder=False, n_jobs=-1).fit(vanco_x_train, vanco_y_train, verbose=False)

# vanco_rf_probs = vanco_rf.predict_proba(vanco_x_train)
# vanco_rf_probs = vanco_rf_probs[:, 1]
# vanco_rf_auc = roc_auc_score(vanco_y_train, vanco_rf_probs)

# print(f'Overall accuracy for Vancouver Random Forest model (training): {vanco_rf.score(vanco_x_train, vanco_y_train):.4f}')
# print(f'ROC AUC for Vancouver Random Forest model (training): {vanco_rf_auc:.4f}')
# print(f'Overall accuracy for Vancouver Random Forest model (validation): {vanco_rf.score(vanco_x_cv, vanco_y_cv):.4f}\n')

#%%
# Tri-Cities Random Forest tuning
# trici_class_weight = trici_y_cv[trici_y_cv == 0].count() / trici_y_cv[trici_y_cv == 1].count()
# trici_hyperparameters = [{'max_depth': np.linspace(1, 10, 10, dtype=int, endpoint=True),
# 						'gamma': np.linspace(1, 10, 10, dtype=int, endpoint=True)}]

# trici_gridsearch = HalvingGridSearchCV(XGBRFClassifier(tree_method='hist', grow_policy='depthwise', subsample=0.8, colsample_bytree=0.8, scale_pos_weight=trici_class_weight, eval_metric='logloss', use_label_encoder=False, n_jobs=-1), trici_hyperparameters, resource='n_estimators', factor=3, min_resources=2, max_resources=500, scoring='roc_auc', cv=5, aggressive_elimination=True, verbose=verbose, n_jobs=-1)
# trici_best_model = trici_gridsearch.fit(trici_x_cv, trici_y_cv)

# print(f'Best Tri-Cities Random Forest parameters: {trici_gridsearch.best_params_}')

#%%
# Tri-Cities Random Forest
# trici_class_weight = trici_y_train[trici_y_train == 0].count() / trici_y_train[trici_y_train == 1].count()
# trici_rf = XGBRFClassifier(tree_method='hist', grow_policy='depthwise', subsample=0.8, colsample_bytree=0.8, scale_pos_weight=trici_class_weight, 
# 								eval_metric='logloss', **trici_gridsearch.best_params_, use_label_encoder=False, n_jobs=-1).fit(trici_x_train, trici_y_train, verbose=False)

# trici_rf_probs = trici_rf.predict_proba(trici_x_train)
# trici_rf_probs = trici_rf_probs[:, 1]
# trici_rf_auc = roc_auc_score(trici_y_train, trici_rf_probs)

# print(f'Overall accuracy for Tri-Cities Random Forest model (training): {trici_rf.score(trici_x_train, trici_y_train):.4f}')
# print(f'ROC AUC for Tri-Cities Random Forest model (training): {trici_rf_auc:.4f}')
# print(f'Overall accuracy for Tri-Cities Random Forest model (validation): {trici_rf.score(trici_x_cv, trici_y_cv):.4f}\n')

#%%
# University Random Forest tuning
# univr_class_weight = univr_y_cv[univr_y_cv == 0].count() / univr_y_cv[univr_y_cv == 1].count()
# univr_hyperparameters = [{'max_depth': np.linspace(1, 10, 10, dtype=int, endpoint=True),
# 						'gamma': np.linspace(1, 10, 10, dtype=int, endpoint=True)}]

# univr_gridsearch = HalvingGridSearchCV(XGBRFClassifier(tree_method='hist', grow_policy='depthwise', subsample=0.8, colsample_bytree=0.8, scale_pos_weight=univr_class_weight, eval_metric='logloss', use_label_encoder=False, n_jobs=-1), univr_hyperparameters, resource='n_estimators', factor=3, min_resources=2, max_resources=500, scoring='roc_auc', cv=5, aggressive_elimination=True, verbose=verbose, n_jobs=-1)
# univr_best_model = univr_gridsearch.fit(univr_x_cv, univr_y_cv)

# print(f'Best University Random Forest parameters: {univr_gridsearch.best_params_}')

#%%
# University Random Forest
# univr_class_weight = univr_y_train[univr_y_train == 0].count() / univr_y_train[univr_y_train == 1].count()
# univr_rf = XGBRFClassifier(tree_method='hist', grow_policy='depthwise', subsample=0.8, colsample_bytree=0.8, scale_pos_weight=univr_class_weight, 
# 								eval_metric='logloss', **univr_gridsearch.best_params_, use_label_encoder=False, n_jobs=-1).fit(univr_x_train, univr_y_train, verbose=False)

# univr_rf_probs = univr_rf.predict_proba(univr_x_train)
# univr_rf_probs = univr_rf_probs[:, 1]
# univr_rf_auc = roc_auc_score(univr_y_train, univr_rf_probs)

# print(f'Overall accuracy for University Random Forest model (training): {univr_rf.score(univr_x_train, univr_y_train):.4f}')
# print(f'ROC AUC for University Random Forest model (training): {univr_rf_auc:.4f}')
# print(f'Overall accuracy for University Random Forest model (validation): {univr_rf.score(univr_x_cv, univr_y_cv):.4f}\n')

#%%
# Pullman XGBoost Random Forest model selection
if build_ft_ft_1yr_prod.DatasetBuilderProd.valid_pass == 0 and build_ft_ft_1yr_prod.DatasetBuilderProd.training_pass == 0:
	pullm_start = time.perf_counter()

	pullm_class_weight = pullm_y_train[pullm_y_train == 0].count() / pullm_y_train[pullm_y_train == 1].count()
	pullm_hyperparameters = [{'max_depth': np.linspace(1, 10, 10, dtype=int, endpoint=True),
							'gamma': np.linspace(1, 10, 10, dtype=int, endpoint=True),
							'learning_rate': [0.01, 0.5, 1.0]}]

	pullm_gridsearch = HalvingGridSearchCV(XGBClassifier(tree_method='hist', grow_policy='depthwise', min_child_weight=min_child_weight, max_bin=max_bin, num_parallel_tree=num_parallel_tree, subsample=subsample, colsample_bytree=colsample_bytree, colsample_bynode=colsample_bynode, scale_pos_weight=pullm_class_weight, eval_metric='logloss', use_label_encoder=False, n_jobs=-1), pullm_hyperparameters, resource='n_estimators', factor=3, min_resources=2, max_resources=500, scoring='roc_auc', cv=5, aggressive_elimination=True, verbose=verbose, n_jobs=-1)
	pullm_best_model = pullm_gridsearch.fit(pullm_x_train, pullm_y_train)

	pullm_stop = time.perf_counter()

	print(f'Pullman XGB Random Forest model trained in {(pullm_stop - pullm_start)/60:.1f} minutes')
	print(f'Best Pullman XGB Random Forest parameters: {pullm_gridsearch.best_params_}')

	pullm_class_weight = pullm_y_train[pullm_y_train == 0].count() / pullm_y_train[pullm_y_train == 1].count()
	pullm_xgbrf = XGBClassifier(tree_method='hist', grow_policy='depthwise', min_child_weight=min_child_weight, max_bin=max_bin, num_parallel_tree=num_parallel_tree, subsample=subsample, colsample_bytree=colsample_bytree, colsample_bynode=colsample_bynode, scale_pos_weight=pullm_class_weight, 
									eval_metric='logloss', **pullm_gridsearch.best_params_, use_label_encoder=False, n_jobs=-1).fit(pullm_x_train, pullm_y_train, eval_set=[(pullm_x_cv, pullm_y_cv)], early_stopping_rounds=20, verbose=False)

	pullm_xgbrf_probs = pullm_xgbrf.predict_proba(pullm_x_train)
	pullm_xgbrf_probs = pullm_xgbrf_probs[:, 1]
	pullm_xgbrf_auc = roc_auc_score(pullm_y_train, pullm_xgbrf_probs)

	print(f'Overall accuracy for Pullman XGB Random Forest model (training): {pullm_xgbrf.score(pullm_x_train, pullm_y_train):.4f}')
	print(f'ROC AUC for Pullman XGB Random Forest model (training): {pullm_xgbrf_auc:.4f}')
	print(f'Overall accuracy for Pullman XGB Random Forest model (validation): {pullm_xgbrf.score(pullm_x_cv, pullm_y_cv):.4f}\n')

else:
	pullm_xgbrf = joblib.load(f'Z:\\Nathan\\Models\\student_risk\\models\\pullm_ft_ft_1yr_model_v{sklearn.__version__}.pkl')

	pullm_xgbrf_probs = pullm_xgbrf.predict_proba(pullm_x_train)
	pullm_xgbrf_probs = pullm_xgbrf_probs[:, 1]
	pullm_xgbrf_auc = roc_auc_score(pullm_y_train, pullm_xgbrf_probs)

	print(f'Overall accuracy for Pullman XGB Random Forest model (training): {pullm_xgbrf.score(pullm_x_train, pullm_y_train):.4f}')
	print(f'ROC AUC for Pullman XGB Random Forest model (training): {pullm_xgbrf_auc:.4f}')
	print(f'Overall accuracy for Pullman XGB Random Forest model (validation): {pullm_xgbrf.score(pullm_x_cv, pullm_y_cv):.4f}\n')

#%%
# Vancouver XGBoost Random Forest model selection
if build_ft_ft_1yr_prod.DatasetBuilderProd.valid_pass == 0 and build_ft_ft_1yr_prod.DatasetBuilderProd.training_pass == 0:
	vanco_start = time.perf_counter()

	vanco_class_weight = vanco_y_train[vanco_y_train == 0].count() / vanco_y_train[vanco_y_train == 1].count()
	vanco_hyperparameters = [{'max_depth': np.linspace(1, 10, 10, dtype=int, endpoint=True),
							'gamma': np.linspace(1, 10, 10, dtype=int, endpoint=True),
							'learning_rate': [0.01, 0.5, 1.0]}]

	vanco_gridsearch = HalvingGridSearchCV(XGBClassifier(tree_method='hist', grow_policy='depthwise', min_child_weight=min_child_weight, max_bin=max_bin, num_parallel_tree=num_parallel_tree, subsample=subsample, colsample_bytree=colsample_bytree, colsample_bynode=colsample_bynode, scale_pos_weight=vanco_class_weight, eval_metric='logloss', use_label_encoder=False, n_jobs=-1), vanco_hyperparameters, resource='n_estimators', factor=3, min_resources=2, max_resources=500, scoring='roc_auc', cv=5, aggressive_elimination=True, verbose=verbose, n_jobs=-1)
	vanco_best_model = vanco_gridsearch.fit(vanco_x_train, vanco_y_train)

	vanco_stop = time.perf_counter()

	print(f'Vancouver XGB Random Forest model trained in {(vanco_stop - vanco_start)/60:.1f} minutes')
	print(f'Best Vancouver XGB Random Forest parameters: {vanco_gridsearch.best_params_}')

	vanco_class_weight = vanco_y_train[vanco_y_train == 0].count() / vanco_y_train[vanco_y_train == 1].count()
	vanco_xgbrf = XGBClassifier(tree_method='hist', grow_policy='depthwise', min_child_weight=min_child_weight, max_bin=max_bin, num_parallel_tree=num_parallel_tree, subsample=subsample, colsample_bytree=colsample_bytree, colsample_bynode=colsample_bynode, scale_pos_weight=vanco_class_weight, 
									eval_metric='logloss', **vanco_gridsearch.best_params_, use_label_encoder=False, n_jobs=-1).fit(vanco_x_train, vanco_y_train, eval_set=[(vanco_x_cv, vanco_y_cv)], early_stopping_rounds=20, verbose=False)

	vanco_xgbrf_probs = vanco_xgbrf.predict_proba(vanco_x_train)
	vanco_xgbrf_probs = vanco_xgbrf_probs[:, 1]
	vanco_xgbrf_auc = roc_auc_score(vanco_y_train, vanco_xgbrf_probs)

	print(f'Overall accuracy for Vancouver XGB Random Forest model (training): {vanco_xgbrf.score(vanco_x_train, vanco_y_train):.4f}')
	print(f'ROC AUC for Vancouver XGB Random Forest model (training): {vanco_xgbrf_auc:.4f}')
	print(f'Overall accuracy for Vancouver XGB Random Forest model (validation): {vanco_xgbrf.score(vanco_x_cv, vanco_y_cv):.4f}\n')

else:
	vanco_xgbrf = joblib.load(f'Z:\\Nathan\\Models\\student_risk\\models\\vanco_ft_ft_1yr_model_v{sklearn.__version__}.pkl')

	vanco_xgbrf_probs = vanco_xgbrf.predict_proba(vanco_x_train)
	vanco_xgbrf_probs = vanco_xgbrf_probs[:, 1]
	vanco_xgbrf_auc = roc_auc_score(vanco_y_train, vanco_xgbrf_probs)

	print(f'Overall accuracy for Vancouver XGB Random Forest model (training): {vanco_xgbrf.score(vanco_x_train, vanco_y_train):.4f}')
	print(f'ROC AUC for Vancouver XGB Random Forest model (training): {vanco_xgbrf_auc:.4f}')
	print(f'Overall accuracy for Vancouver XGB Random Forest model (validation): {vanco_xgbrf.score(vanco_x_cv, vanco_y_cv):.4f}\n')

#%%
# Tri-Cities XGBoost Random Forest model selection
if build_ft_ft_1yr_prod.DatasetBuilderProd.valid_pass == 0 and build_ft_ft_1yr_prod.DatasetBuilderProd.training_pass == 0:
	trici_start = time.perf_counter()

	trici_class_weight = trici_y_train[trici_y_train == 0].count() / trici_y_train[trici_y_train == 1].count()
	trici_hyperparameters = [{'max_depth': np.linspace(1, 10, 10, dtype=int, endpoint=True),
							'gamma': np.linspace(1, 10, 10, dtype=int, endpoint=True),
							'learning_rate': [0.01, 0.5, 1.0]}]

	trici_gridsearch = HalvingGridSearchCV(XGBClassifier(tree_method='hist', grow_policy='depthwise', min_child_weight=min_child_weight, max_bin=max_bin, num_parallel_tree=num_parallel_tree, subsample=subsample, colsample_bytree=colsample_bytree, colsample_bynode=colsample_bynode, scale_pos_weight=trici_class_weight, eval_metric='logloss', use_label_encoder=False, n_jobs=-1), trici_hyperparameters, resource='n_estimators', factor=3, min_resources=2, max_resources=500, scoring='roc_auc', cv=5, aggressive_elimination=True, verbose=verbose, n_jobs=-1)
	trici_best_model = trici_gridsearch.fit(trici_x_train, trici_y_train)

	trici_stop = time.perf_counter()

	print(f'Tri-Cities XGB Random Forest model trained in {(trici_stop - trici_start)/60:.1f} minutes')
	print(f'Best Tri-Cities XGB Random Forest parameters: {trici_gridsearch.best_params_}')

	trici_class_weight = trici_y_train[trici_y_train == 0].count() / trici_y_train[trici_y_train == 1].count()
	trici_xgbrf = XGBClassifier(tree_method='hist', grow_policy='depthwise', min_child_weight=min_child_weight, max_bin=max_bin, num_parallel_tree=num_parallel_tree, subsample=subsample, colsample_bytree=colsample_bytree, colsample_bynode=colsample_bynode, scale_pos_weight=trici_class_weight, 
									eval_metric='logloss', **trici_gridsearch.best_params_, use_label_encoder=False, n_jobs=-1).fit(trici_x_train, trici_y_train, eval_set=[(trici_x_cv, trici_y_cv)], early_stopping_rounds=20, verbose=False)

	trici_xgbrf_probs = trici_xgbrf.predict_proba(trici_x_train)
	trici_xgbrf_probs = trici_xgbrf_probs[:, 1]
	trici_xgbrf_auc = roc_auc_score(trici_y_train, trici_xgbrf_probs)

	print(f'Overall accuracy for Tri-Cities XGB Random Forest model (training): {trici_xgbrf.score(trici_x_train, trici_y_train):.4f}')
	print(f'ROC AUC for Tri-Cities XGB Random Forest model (training): {trici_xgbrf_auc:.4f}')
	print(f'Overall accuracy for Tri-Cities XGB Random Forest model (validation): {trici_xgbrf.score(trici_x_cv, trici_y_cv):.4f}\n')

else:
	trici_xgbrf = joblib.load(f'Z:\\Nathan\\Models\\student_risk\\models\\trici_ft_ft_1yr_model_v{sklearn.__version__}.pkl')

	trici_xgbrf_probs = trici_xgbrf.predict_proba(trici_x_train)
	trici_xgbrf_probs = trici_xgbrf_probs[:, 1]
	trici_xgbrf_auc = roc_auc_score(trici_y_train, trici_xgbrf_probs)

	print(f'Overall accuracy for Tri-Cities XGB Random Forest model (training): {trici_xgbrf.score(trici_x_train, trici_y_train):.4f}')
	print(f'ROC AUC for Tri-Cities XGB Random Forest model (training): {trici_xgbrf_auc:.4f}')
	print(f'Overall accuracy for Tri-Cities XGB Random Forest model (validation): {trici_xgbrf.score(trici_x_cv, trici_y_cv):.4f}\n')

#%%
# University XGBoost Random Forest model selection
if build_ft_ft_1yr_prod.DatasetBuilderProd.valid_pass == 0 and build_ft_ft_1yr_prod.DatasetBuilderProd.training_pass == 0:
	univr_start = time.perf_counter()

	univr_class_weight = univr_y_train[univr_y_train == 0].count() / univr_y_train[univr_y_train == 1].count()
	univr_hyperparameters = [{'max_depth': np.linspace(1, 10, 10, dtype=int, endpoint=True),
							'gamma': np.linspace(1, 10, 10, dtype=int, endpoint=True),
							'learning_rate': [0.01, 0.5, 1.0]}]

	univr_gridsearch = HalvingGridSearchCV(XGBClassifier(tree_method='hist', grow_policy='depthwise', min_child_weight=min_child_weight, max_bin=max_bin, num_parallel_tree=num_parallel_tree, subsample=subsample, colsample_bytree=colsample_bytree, colsample_bynode=colsample_bynode, scale_pos_weight=univr_class_weight, eval_metric='logloss', use_label_encoder=False, n_jobs=-1), univr_hyperparameters, resource='n_estimators', factor=3, min_resources=2, max_resources=500, scoring='roc_auc', cv=5, aggressive_elimination=True, verbose=verbose, n_jobs=-1)
	univr_best_model = univr_gridsearch.fit(univr_x_train, univr_y_train)

	univr_stop = time.perf_counter()

	print(f'University XGB Random Forest model trained in {(univr_stop - univr_start)/60:.1f} minutes')
	print(f'Best University XGB Random Forest parameters: {univr_gridsearch.best_params_}')

	univr_class_weight = univr_y_train[univr_y_train == 0].count() / univr_y_train[univr_y_train == 1].count()
	univr_xgbrf = XGBClassifier(tree_method='hist', grow_policy='depthwise', min_child_weight=min_child_weight, max_bin=max_bin, num_parallel_tree=num_parallel_tree, subsample=subsample, colsample_bytree=colsample_bytree, colsample_bynode=colsample_bynode, scale_pos_weight=univr_class_weight, 
									eval_metric='logloss', **univr_gridsearch.best_params_, use_label_encoder=False, n_jobs=-1).fit(univr_x_train, univr_y_train, eval_set=[(univr_x_cv, univr_y_cv)], early_stopping_rounds=20, verbose=False)

	univr_xgbrf_probs = univr_xgbrf.predict_proba(univr_x_train)
	univr_xgbrf_probs = univr_xgbrf_probs[:, 1]
	univr_xgbrf_auc = roc_auc_score(univr_y_train, univr_xgbrf_probs)

	print(f'Overall accuracy for University XGB Random Forest model (training): {univr_xgbrf.score(univr_x_train, univr_y_train):.4f}')
	print(f'ROC AUC for University XGB Random Forest model (training): {univr_xgbrf_auc:.4f}')
	print(f'Overall accuracy for University XGB Random Forest model (validation): {univr_xgbrf.score(univr_x_cv, univr_y_cv):.4f}\n')

else:
	univr_xgbrf = joblib.load(f'Z:\\Nathan\\Models\\student_risk\\models\\univr_ft_ft_1yr_model_v{sklearn.__version__}.pkl')

	univr_xgbrf_probs = univr_xgbrf.predict_proba(univr_x_train)
	univr_xgbrf_probs = univr_xgbrf_probs[:, 1]
	univr_xgbrf_auc = roc_auc_score(univr_y_train, univr_xgbrf_probs)

	print(f'Overall accuracy for University XGB Random Forest model (training): {univr_xgbrf.score(univr_x_train, univr_y_train):.4f}')
	print(f'ROC AUC for University XGB Random Forest model (training): {univr_xgbrf_auc:.4f}')
	print(f'Overall accuracy for University XGB Random Forest model (validation): {univr_xgbrf.score(univr_x_cv, univr_y_cv):.4f}\n')

#%%
# Ensemble model

# Pullman VCF
# pullm_vcf = VotingClassifier(estimators=[('lreg', pullm_lreg), ('sgd', pullm_sgd)], voting='soft', weights=[1, 1]).fit(pullm_x_train, pullm_y_train)

# pullm_vcf_probs = pullm_vcf.predict_proba(pullm_x_train)
# pullm_vcf_probs = pullm_vcf_probs[:, 1]
# pullm_vcf_auc = roc_auc_score(pullm_y_train, pullm_vcf_probs)

# print(f'\nOverall accuracy for Pullman ensemble model (training): {pullm_vcf.score(pullm_x_train, pullm_y_train):.4f}')
# print(f'ROC AUC for Pullman ensemble model (training): {pullm_vcf_auc:.4f}\n')

#%%
# Vancouver VCF
# vanco_vcf = VotingClassifier(estimators=[('lreg', vanco_lreg), ('sgd', vanco_sgd)], voting='soft', weights=[1, 1]).fit(vanco_x_train, vanco_y_train)

# vanco_vcf_probs = vanco_vcf.predict_proba(vanco_x_train)
# vanco_vcf_probs = vanco_vcf_probs[:, 1]
# vanco_vcf_auc = roc_auc_score(vanco_y_train, vanco_vcf_probs)

# print(f'\nOverall accuracy for Vancouver ensemble model (training): {vanco_vcf.score(vanco_x_train, vanco_y_train):.4f}')
# print(f'ROC AUC for Vancouver ensemble model (training): {vanco_vcf_auc:.4f}\n')

#%%
# Tri-Cities VCF
# trici_vcf = VotingClassifier(estimators=[('lreg', trici_lreg), ('sgd', trici_sgd)], voting='soft', weights=[1, 1]).fit(trici_x_train, trici_y_train)

# trici_vcf_probs = trici_vcf.predict_proba(trici_x_train)
# trici_vcf_probs = trici_vcf_probs[:, 1]
# trici_vcf_auc = roc_auc_score(trici_y_train, trici_vcf_probs)

# print(f'\nOverall accuracy for Tri-Cities ensemble model (training): {trici_vcf.score(trici_x_train, trici_y_train):.4f}')
# print(f'ROC AUC for Tri-Cities ensemble model (training): {trici_vcf_auc:.4f}\n')

#%%
# University VCF
# univr_vcf = VotingClassifier(estimators=[('lreg', univr_lreg), ('sgd', univr_sgd)], voting='soft', weights=[1, 1]).fit(univr_x_train, univr_y_train)

# univr_vcf_probs = univr_vcf.predict_proba(univr_x_train)
# univr_vcf_probs = univr_vcf_probs[:, 1]
# univr_vcf_auc = roc_auc_score(univr_y_train, univr_vcf_probs)

# print(f'\nOverall accuracy for University ensemble model (training): {univr_vcf.score(univr_x_train, univr_y_train):.4f}')
# print(f'ROC AUC for University ensemble model (training): {univr_vcf_auc:.4f}\n')

#%%
print('Calculate SHAP values...')

# Pullman SHAP training (see: https://github.com/slundberg/shap)
pullm_explainer = shap.TreeExplainer(model=pullm_xgbrf, data=pullm_x_train, model_output='predict_proba')

#%%
# Pullman SHAP prediction
pullm_shap_values = pullm_explainer.shap_values(X=pullm_x_test)

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
# Vancouver SHAP training (see: https://github.com/slundberg/shap)
vanco_explainer = shap.TreeExplainer(model=vanco_xgbrf, data=vanco_x_train, model_output='predict_proba')

#%%
# Vancouver SHAP prediction
vanco_shap_values = vanco_explainer.shap_values(X=vanco_x_test)

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
# Tri-Cities SHAP training (see: https://github.com/slundberg/shap)
trici_explainer = shap.TreeExplainer(model=trici_xgbrf, data=trici_x_train, model_output='predict_proba')

#%%
# Tri-Cities SHAP prediction
trici_shap_values = trici_explainer.shap_values(X=trici_x_test)

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
# University SHAP training (see: https://github.com/slundberg/shap)
univr_explainer = shap.TreeExplainer(model=univr_xgbrf, data=univr_x_train, model_output='predict_proba')

#%%
# University SHAP prediction
univr_shap_values = univr_explainer.shap_values(X=univr_x_test)

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
# pullm_lreg_pred_probs = pullm_lreg.predict_proba(pullm_x_test)
# pullm_lreg_pred_probs = pullm_lreg_pred_probs[:, 1]
# pullm_sgd_pred_probs = pullm_sgd.predict_proba(pullm_x_test)
# pullm_sgd_pred_probs = pullm_sgd_pred_probs[:, 1]
# pullm_xgb_pred_probs = pullm_xgb.predict_proba(pullm_x_test)
# pullm_xgb_pred_probs = pullm_xgb_pred_probs[:, 1]
# pullm_rf_pred_probs = pullm_rf.predict_proba(pullm_x_test)
# pullm_rf_pred_probs = pullm_rf_pred_probs[:, 1]
pullm_xgbrf_pred_probs = pullm_xgbrf.predict_proba(pullm_x_test)
pullm_xgbrf_pred_probs = pullm_xgbrf_pred_probs[:, 1]
# pullm_mlp_pred_probs = pullm_mlp.predict_proba(pullm_x_test)
# pullm_mlp_pred_probs = pullm_mlp_pred_probs[:, 1]
# pullm_vcf_pred_probs = pullm_vcf.predict_proba(pullm_x_test)
# pullm_vcf_pred_probs = pullm_vcf_pred_probs[:, 1]

#%%
# Vancouver probabilites
# vanco_lreg_pred_probs = vanco_lreg.predict_proba(vanco_x_test)
# vanco_lreg_pred_probs = vanco_lreg_pred_probs[:, 1]
# vanco_sgd_pred_probs = vanco_sgd.predict_proba(vanco_x_test)
# vanco_sgd_pred_probs = vanco_sgd_pred_probs[:, 1]
# vanco_xgb_pred_probs = vanco_xgb.predict_proba(vanco_x_test)
# vanco_xgb_pred_probs = vanco_xgb_pred_probs[:, 1]
# vanco_rf_pred_probs = vanco_rf.predict_proba(vanco_x_test)
# vanco_rf_pred_probs = vanco_rf_pred_probs[:, 1]
vanco_xgbrf_pred_probs = vanco_xgbrf.predict_proba(vanco_x_test)
vanco_xgbrf_pred_probs = vanco_xgbrf_pred_probs[:, 1]
# vanco_mlp_pred_probs = vanco_mlp.predict_proba(vanco_x_test)
# vanco_mlp_pred_probs = vanco_mlp_pred_probs[:, 1]
# vanco_vcf_pred_probs = vanco_vcf.predict_proba(vanco_x_test)
# vanco_vcf_pred_probs = vanco_vcf_pred_probs[:, 1]

#%%
# Tri-Cities probabilities
# trici_lreg_pred_probs = trici_lreg.predict_proba(trici_x_test)
# trici_lreg_pred_probs = trici_lreg_pred_probs[:, 1]
# trici_sgd_pred_probs = trici_sgd.predict_proba(trici_x_test)
# trici_sgd_pred_probs = trici_sgd_pred_probs[:, 1]
# trici_xgb_pred_probs = trici_xgb.predict_proba(trici_x_test)
# trici_xgb_pred_probs = trici_xgb_pred_probs[:, 1]
# trici_rf_pred_probs = trici_rf.predict_proba(trici_x_test)
# trici_rf_pred_probs = trici_rf_pred_probs[:, 1]
trici_xgbrf_pred_probs = trici_xgbrf.predict_proba(trici_x_test)
trici_xgbrf_pred_probs = trici_xgbrf_pred_probs[:, 1]
# trici_mlp_pred_probs = trici_mlp.predict_proba(trici_x_test)
# trici_mlp_pred_probs = trici_mlp_pred_probs[:, 1]
# trici_vcf_pred_probs = trici_vcf.predict_proba(trici_x_test)
# trici_vcf_pred_probs = trici_vcf_pred_probs[:, 1]

#%%
# University probabilities
# univr_lreg_pred_probs = univr_lreg.predict_proba(univr_x_test)
# univr_lreg_pred_probs = univr_lreg_pred_probs[:, 1]
# univr_sgd_pred_probs = univr_sgd.predict_proba(univr_x_test)
# univr_sgd_pred_probs = univr_sgd_pred_probs[:, 1]
# univr_xgb_pred_probs = univr_xgb.predict_proba(univr_x_test)
# univr_xgb_pred_probs = univr_xgb_pred_probs[:, 1]
# univr_rf_pred_probs = univr_rf.predict_proba(univr_x_test)
# univr_rf_pred_probs = univr_rf_pred_probs[:, 1]
univr_xgbrf_pred_probs = univr_xgbrf.predict_proba(univr_x_test)
univr_xgbrf_pred_probs = univr_xgbrf_pred_probs[:, 1]
# univr_mlp_pred_probs = univr_mlp.predict_proba(univr_x_test)
# univr_mlp_pred_probs = univr_mlp_pred_probs[:, 1]
# univr_vcf_pred_probs = univr_vcf.predict_proba(univr_x_test)
# univr_vcf_pred_probs = univr_vcf_pred_probs[:, 1]

print('Done\n')

#%%
# Output model predictions to file
print('Output model predictions and model...')

# Pullman predicted outcome
# pullm_pred_outcome['lr_prob'] = pd.DataFrame(pullm_lreg_pred_probs)
# pullm_pred_outcome['lr_pred'] = pullm_lreg.predict(pullm_x_test)
# pullm_pred_outcome['sgd_prob'] = pd.DataFrame(pullm_sgd_pred_probs)
# pullm_pred_outcome['sgd_pred'] = pullm_sgd.predict(pullm_x_test)
# pullm_pred_outcome['xgb_prob'] = pd.DataFrame(pullm_xgb_pred_probs)
# pullm_pred_outcome['xgb_pred'] = pullm_xgb.predict(pullm_x_test)
# pullm_pred_outcome['rf_prob'] = pd.DataFrame(pullm_rf_pred_probs)
# pullm_pred_outcome['rf_pred'] = pullm_rf.predict(pullm_x_test)
pullm_pred_outcome['xgbrf_prob'] = pd.DataFrame(pullm_xgbrf_pred_probs)
pullm_pred_outcome['xgbrf_pred'] = pullm_xgbrf.predict(pullm_x_test)
# pullm_pred_outcome['mlp_prob'] = pd.DataFrame(pullm_mlp_pred_probs)
# pullm_pred_outcome['mlp_pred'] = pullm_mlp.predict(pullm_x_test)
# pullm_pred_outcome['vcf_prob'] = pd.DataFrame(pullm_vcf_pred_probs)
# pullm_pred_outcome['vcf_pred'] = pullm_vcf.predict(pullm_x_test)
pullm_pred_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\pullm\\pullm_ft_ft_1yr_pred_outcome.csv', encoding='utf-8', index=False)

#%%
# Vancouver predicted outcome
# vanco_pred_outcome['lr_prob'] = pd.DataFrame(vanco_lreg_pred_probs)
# vanco_pred_outcome['lr_pred'] = vanco_lreg.predict(vanco_x_test)
# vanco_pred_outcome['sgd_prob'] = pd.DataFrame(vanco_sgd_pred_probs)
# vanco_pred_outcome['sgd_pred'] = vanco_sgd.predict(vanco_x_test)
# vanco_pred_outcome['xgb_prob'] = pd.DataFrame(vanco_xgb_pred_probs)
# vanco_pred_outcome['xgb_pred'] = vanco_xgb.predict(vanco_x_test)
# vanco_pred_outcome['rf_prob'] = pd.DataFrame(vanco_rf_pred_probs)
# vanco_pred_outcome['rf_pred'] = vanco_rf.predict(vanco_x_test)
vanco_pred_outcome['xgbrf_prob'] = pd.DataFrame(vanco_xgbrf_pred_probs)
vanco_pred_outcome['xgbrf_pred'] = vanco_xgbrf.predict(vanco_x_test)
# vanco_pred_outcome['mlp_prob'] = pd.DataFrame(vanco_mlp_pred_probs)
# vanco_pred_outcome['mlp_pred'] = vanco_mlp.predict(vanco_x_test)
# vanco_pred_outcome['vcf_prob'] = pd.DataFrame(vanco_vcf_pred_probs)
# vanco_pred_outcome['vcf_pred'] = vanco_vcf.predict(vanco_x_test)
vanco_pred_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\vanco\\vanco_ft_ft_1yr_pred_outcome.csv', encoding='utf-8', index=False)

#%%
# Tri-Cities predicted outcome
# trici_pred_outcome['lr_prob'] = pd.DataFrame(trici_lreg_pred_probs)
# trici_pred_outcome['lr_pred'] = trici_lreg.predict(trici_x_test)
# trici_pred_outcome['sgd_prob'] = pd.DataFrame(trici_sgd_pred_probs)
# trici_pred_outcome['sgd_pred'] = trici_sgd.predict(trici_x_test)
# trici_pred_outcome['xgb_prob'] = pd.DataFrame(trici_xgb_pred_probs)
# trici_pred_outcome['xgb_pred'] = trici_xgb.predict(trici_x_test)
# trici_pred_outcome['rf_prob'] = pd.DataFrame(trici_rf_pred_probs)
# trici_pred_outcome['rf_pred'] = trici_rf.predict(trici_x_test)
trici_pred_outcome['xgbrf_prob'] = pd.DataFrame(trici_xgbrf_pred_probs)
trici_pred_outcome['xgbrf_pred'] = trici_xgbrf.predict(trici_x_test)
# trici_pred_outcome['mlp_prob'] = pd.DataFrame(trici_mlp_pred_probs)
# trici_pred_outcome['mlp_pred'] = trici_mlp.predict(trici_x_test)
# trici_pred_outcome['vcf_prob'] = pd.DataFrame(trici_vcf_pred_probs)
# trici_pred_outcome['vcf_pred'] = trici_vcf.predict(trici_x_test)
trici_pred_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\trici\\trici_ft_ft_1yr_pred_outcome.csv', encoding='utf-8', index=False)

#%%
# University predicted outcome
# univr_pred_outcome['lr_prob'] = pd.DataFrame(univr_lreg_pred_probs)
# univr_pred_outcome['lr_pred'] = univr_lreg.predict(univr_x_test)
# univr_pred_outcome['sgd_prob'] = pd.DataFrame(univr_sgd_pred_probs)
# univr_pred_outcome['sgd_pred'] = univr_sgd.predict(univr_x_test)
# univr_pred_outcome['xgb_prob'] = pd.DataFrame(univr_xgb_pred_probs)
# univr_pred_outcome['xgb_pred'] = univr_xgb.predict(univr_x_test)
# univr_pred_outcome['rf_prob'] = pd.DataFrame(univr_rf_pred_probs)
# univr_pred_outcome['rf_pred'] = univr_rf.predict(univr_x_test)
univr_pred_outcome['xgbrf_prob'] = pd.DataFrame(univr_xgbrf_pred_probs)
univr_pred_outcome['xgbrf_pred'] = univr_xgbrf.predict(univr_x_test)
# univr_pred_outcome['mlp_prob'] = pd.DataFrame(univr_mlp_pred_probs)
# univr_pred_outcome['mlp_pred'] = univr_mlp.predict(univr_x_test)
# univr_pred_outcome['vcf_prob'] = pd.DataFrame(univr_vcf_pred_probs)
# univr_pred_outcome['vcf_pred'] = univr_vcf.predict(univr_x_test)
univr_pred_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\univr\\univr_ft_ft_1yr_pred_outcome.csv', encoding='utf-8', index=False)

#%%
# Pullman aggregate outcome
pullm_aggregate_outcome['emplid'] = pullm_aggregate_outcome['emplid'].astype(str).str.zfill(9)
pullm_aggregate_outcome['risk_prob'] = 1 - pd.DataFrame(pullm_xgbrf_pred_probs).round(4)

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

pullm_aggregate_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\pullm\\pullm_ft_ft_1yr_aggregate_outcome.csv', encoding='utf-8', index=False)

#%%
# Vancouver aggregate outcome
vanco_aggregate_outcome['emplid'] = vanco_aggregate_outcome['emplid'].astype(str).str.zfill(9)
vanco_aggregate_outcome['risk_prob'] = 1 - pd.DataFrame(vanco_xgbrf_pred_probs).round(4)

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

vanco_aggregate_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\vanco\\vanco_ft_ft_1yr_aggregate_outcome.csv', encoding='utf-8', index=False)

#%%
# Tri-Cities aggregate outcome
trici_aggregate_outcome['emplid'] = trici_aggregate_outcome['emplid'].astype(str).str.zfill(9)
trici_aggregate_outcome['risk_prob'] = 1 - pd.DataFrame(trici_xgbrf_pred_probs).round(4)

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

trici_aggregate_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\trici\\trici_ft_ft_1yr_aggregate_outcome.csv', encoding='utf-8', index=False)

#%%
# University aggregate outcome
univr_aggregate_outcome['emplid'] = univr_aggregate_outcome['emplid'].astype(str).str.zfill(9)
univr_aggregate_outcome['risk_prob'] = 1 - pd.DataFrame(univr_xgbrf_pred_probs).round(4)

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

univr_aggregate_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\univr\\univr_ft_ft_1yr_aggregate_outcome.csv', encoding='utf-8', index=False)

#%%
# Pullman current outcome
pullm_current_outcome['emplid'] = pullm_current_outcome['emplid'].astype(str).str.zfill(9)
pullm_current_outcome['risk_prob'] = 1 - pd.DataFrame(pullm_xgbrf_pred_probs).round(4)

pullm_current_outcome['date'] = run_date
pullm_current_outcome['model_id'] = model_id

#%%
# Vancouver current outcome
vanco_current_outcome['emplid'] = vanco_current_outcome['emplid'].astype(str).str.zfill(9)
vanco_current_outcome['risk_prob'] = 1 - pd.DataFrame(vanco_xgbrf_pred_probs).round(4)

vanco_current_outcome['date'] = run_date
vanco_current_outcome['model_id'] = model_id

#%%
# Tri-Cities current outcome
trici_current_outcome['emplid'] = trici_current_outcome['emplid'].astype(str).str.zfill(9)
trici_current_outcome['risk_prob'] = 1 - pd.DataFrame(trici_xgbrf_pred_probs).round(4)

trici_current_outcome['date'] = run_date
trici_current_outcome['model_id'] = model_id

#%%
# University current outcome
univr_current_outcome['emplid'] = univr_current_outcome['emplid'].astype(str).str.zfill(9)
univr_current_outcome['risk_prob'] = 1 - pd.DataFrame(univr_xgbrf_pred_probs).round(4)

univr_current_outcome['date'] = run_date
univr_current_outcome['model_id'] = model_id

#%%
# Pullman to csv and to sql
if not os.path.isfile('Z:\\Nathan\\Models\\student_risk\\predictions\\pullm\\pullm_ft_ft_1yr_student_outcome.csv'):
	pullm_current_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\pullm\\pullm_ft_ft_1yr_student_outcome.csv', encoding='utf-8', index=False)
	pullm_current_outcome.to_sql('student_outcome', con=auto_engine, if_exists='append', index=False, schema='oracle_int.dbo')
else:
	pullm_prior_outcome = pd.read_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\pullm\\pullm_ft_ft_1yr_student_outcome.csv', encoding='utf-8', low_memory=False)
	pullm_prior_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\pullm\\pullm_ft_ft_1yr_student_backup.csv', encoding='utf-8', index=False)
	pullm_student_outcome = pd.concat([pullm_prior_outcome, pullm_current_outcome])
	pullm_student_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\pullm\\pullm_ft_ft_1yr_student_outcome.csv', encoding='utf-8', index=False)
	pullm_current_outcome.to_sql('student_outcome', con=auto_engine, if_exists='append', index=False, schema='oracle_int.dbo')

#%%
# Vancouver to csv and to sql
if not os.path.isfile('Z:\\Nathan\\Models\\student_risk\\predictions\\vanco\\vanco_ft_ft_1yr_student_outcome.csv'):
	vanco_current_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\vanco\\vanco_ft_ft_1yr_student_outcome.csv', encoding='utf-8', index=False)
	vanco_current_outcome.to_sql('student_outcome', con=auto_engine, if_exists='append', index=False, schema='oracle_int.dbo')
else:
	vanco_prior_outcome = pd.read_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\vanco\\vanco_ft_ft_1yr_student_outcome.csv', encoding='utf-8', low_memory=False)
	vanco_prior_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\vanco\\vanco_ft_ft_1yr_student_backup.csv', encoding='utf-8', index=False)
	vanco_student_outcome = pd.concat([vanco_prior_outcome, vanco_current_outcome])
	vanco_student_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\vanco\\vanco_ft_ft_1yr_student_outcome.csv', encoding='utf-8', index=False)
	vanco_current_outcome.to_sql('student_outcome', con=auto_engine, if_exists='append', index=False, schema='oracle_int.dbo')

#%%
# Tri-Cities to csv and to sql
if not os.path.isfile('Z:\\Nathan\\Models\\student_risk\\predictions\\trici\\trici_ft_ft_1yr_student_outcome.csv'):
	trici_current_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\trici\\trici_ft_ft_1yr_student_outcome.csv', encoding='utf-8', index=False)
	trici_current_outcome.to_sql('student_outcome', con=auto_engine, if_exists='append', index=False, schema='oracle_int.dbo')
else:
	trici_prior_outcome = pd.read_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\trici\\trici_ft_ft_1yr_student_outcome.csv', encoding='utf-8', low_memory=False)
	trici_prior_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\trici\\trici_ft_ft_1yr_student_backup.csv', encoding='utf-8', index=False)
	trici_student_outcome = pd.concat([trici_prior_outcome, trici_current_outcome])
	trici_student_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\trici\\trici_ft_ft_1yr_student_outcome.csv', encoding='utf-8', index=False)
	trici_current_outcome.to_sql('student_outcome', con=auto_engine, if_exists='append', index=False, schema='oracle_int.dbo')

#%%
# University to csv and to sql
if not os.path.isfile('Z:\\Nathan\\Models\\student_risk\\predictions\\univr\\univr_ft_ft_1yr_student_outcome.csv'):
	univr_current_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\univr\\univr_ft_ft_1yr_student_outcome.csv', encoding='utf-8', index=False)
	univr_current_outcome.to_sql('student_outcome', con=auto_engine, if_exists='append', index=False, schema='oracle_int.dbo')
else:
	univr_prior_outcome = pd.read_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\univr\\univr_ft_ft_1yr_student_outcome.csv', encoding='utf-8', low_memory=False)
	univr_prior_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\univr\\univr_ft_ft_1yr_student_backup.csv', encoding='utf-8', index=False)
	univr_student_outcome = pd.concat([univr_prior_outcome, univr_current_outcome])
	univr_student_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\univr\\univr_ft_ft_1yr_student_outcome.csv', encoding='utf-8', index=False)
	univr_current_outcome.to_sql('student_outcome', con=auto_engine, if_exists='append', index=False, schema='oracle_int.dbo')

#%%
# Pullman top-N SHAP values to csv and to sql
pullm_shap_file = open('Z:\\Nathan\\Models\\student_risk\\shap\\pullm\\pullm_ft_ft_1yr_shap.csv', 'w', newline='')
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
vanco_shap_file = open('Z:\\Nathan\\Models\\student_risk\\shap\\vanco\\vanco_ft_ft_1yr_shap.csv', 'w', newline='')
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
trici_shap_file = open('Z:\\Nathan\\Models\\student_risk\\shap\\trici\\trici_ft_ft_1yr_shap.csv', 'w', newline='')
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
univr_shap_file = open('Z:\\Nathan\\Models\\student_risk\\shap\\univr\\univr_ft_ft_1yr_shap.csv', 'w', newline='')
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
joblib.dump(pullm_xgbrf, f'Z:\\Nathan\\Models\\student_risk\\models\\pullm_ft_ft_1yr_model_v{sklearn.__version__}.pkl')

#%%
# Vancouver model output
joblib.dump(vanco_xgbrf, f'Z:\\Nathan\\Models\\student_risk\\models\\vanco_ft_ft_1yr_model_v{sklearn.__version__}.pkl')

#%%
# Tri-Cities model output
joblib.dump(trici_xgbrf, f'Z:\\Nathan\\Models\\student_risk\\models\\trici_ft_ft_1yr_model_v{sklearn.__version__}.pkl')

#%%
# University model output
joblib.dump(univr_xgbrf, f'Z:\\Nathan\\Models\\student_risk\\models\\univr_ft_ft_1yr_model_v{sklearn.__version__}.pkl')

print('Done\n')