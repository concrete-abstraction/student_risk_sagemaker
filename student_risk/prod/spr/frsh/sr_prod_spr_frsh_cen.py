#%%
from student_risk import build_prod, config
import datetime
import joblib
import numpy as np
import pandas as pd
import pathlib
import pyodbc
import os
import saspy
import sklearn
import sqlalchemy
import urllib
from datetime import date
from patsy import dmatrices
from imblearn.under_sampling import TomekLinks
from sklearn.compose import make_column_transformer
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.ensemble import VotingClassifier
from sklearn.metrics import roc_curve, roc_auc_score
from statsmodels.discrete.discrete_model import Logit
from statsmodels.stats.outliers_influence import variance_inflation_factor

#%%
# Database connection
cred = pathlib.Path('Z:\\Nathan\\Models\\student_risk\\login.bin').read_text().split('|')
params = urllib.parse.quote_plus(f'TRUSTED_CONNECTION=YES; DRIVER={{SQL Server Native Client 11.0}}; SERVER={cred[0]}; DATABASE={cred[1]}')
engine = sqlalchemy.create_engine(f'mssql+pyodbc:///?odbc_connect={params}')
auto_engine = engine.execution_options(autocommit=True, isolation_level='AUTOCOMMIT')

#%%
# Global variable intialization
strm = None

#%%
# Census date and snapshot check 
calendar = pd.read_csv('Z:\\Nathan\\Models\\student_risk\\supplemental_files\\acad_calendar.csv', encoding='utf-8', parse_dates=True).fillna(9999)
now = datetime.datetime.now()

now_day = now.day
now_month = now.month
now_year = now.year

strm = calendar[(calendar['term_year'] == now_year) & (calendar['begin_month'] <= now_month) & (calendar['end_month'] >= now_month)]['STRM'].values[0]

census_day = calendar[(calendar['term_year'] == now_year) & (calendar['begin_month'] <= now_month) & (calendar['end_month'] >= now_month)]['census_day'].values[0]
census_month = calendar[(calendar['term_year'] == now_year) & (calendar['begin_month'] <= now_month) & (calendar['end_month'] >= now_month)]['census_month'].values[0]
census_year = calendar[(calendar['term_year'] == now_year) & (calendar['begin_month'] <= now_month) & (calendar['end_month'] >= now_month)]['census_year'].values[0]

if now_year < census_year:
	raise config.CenError(f'{date.today()}: Census year exception, attempting to run if census newest snapshot.')

elif (now_year == census_year and now_month < census_month):
	raise config.CenError(f'{date.today()}: Census month exception, attempting to run if census newest snapshot.')

elif (now_year == census_year and now_month == census_month and now_day < census_day):
	raise config.CenError(f'{date.today()}: Census day exception, attempting to run if census newest snapshot.')

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
						# 'distance',
						'pop_dens',
						'underrep_minority', 
						# 'ipeds_ethnic_group_descrshort',
						'pell_eligibility_ind', 
						# 'pell_recipient_ind',
						'first_gen_flag', 
						# 'LSAMP_STEM_Flag',
						# 'anywhere_STEM_Flag',
						'honors_program_ind',
						# 'afl_greek_indicator',
						# 'high_school_gpa',
						'fall_term_gpa',
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
						'total_spring_contact_hrs',
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
						'gini_indx',
						# 'pvrt_rate',
						'median_inc',
						# 'median_value',
						'educ_rate',
						'pct_blk',
						'pct_ai',
						# 'pct_asn',
						'pct_hawi',
						# 'pct_oth',
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
						# 'term_credit_hours',
						# 'total_fall_units',
						'spring_withdrawn_hours',
						# 'athlete',
						'remedial',
						# 'ACAD_PLAN',
						# 'plan_owner_org',
						'business',
						'cahnrs_anml',
						'cahnrs_envr',
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
						'pharmacy',
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
						'unmet_need_ofr'
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
							# 'distance',
							'pop_dens',
							'underrep_minority', 
							# 'ipeds_ethnic_group_descrshort',
							'pell_eligibility_ind', 
							# 'pell_recipient_ind',
							'first_gen_flag', 
							# 'LSAMP_STEM_Flag',
							# 'anywhere_STEM_Flag',
							'honors_program_ind',
							# 'afl_greek_indicator',
							# 'high_school_gpa',
							'fall_term_gpa',
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
							'total_spring_contact_hrs',
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
							'gini_indx',
							# 'pvrt_rate',
							'median_inc',
							# 'median_value',
							'educ_rate',
							'pct_blk',
							'pct_ai',
							# 'pct_asn',
							'pct_hawi',
							# 'pct_oth',
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
							# 'term_credit_hours',
							# 'total_fall_units',
							'spring_withdrawn_hours',
							# 'athlete',
							'remedial',
							# 'ACAD_PLAN',
							# 'plan_owner_org',
							'business',
							'cahnrs_anml',
							'cahnrs_envr',
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
							'pharmacy',
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
							'unmet_need_ofr'
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
							# 'distance',
							'pop_dens',
							'underrep_minority', 
							# 'ipeds_ethnic_group_descrshort',
							'pell_eligibility_ind', 
							# 'pell_recipient_ind',
							'first_gen_flag', 
							# 'LSAMP_STEM_Flag',
							# 'anywhere_STEM_Flag',
							'honors_program_ind',
							# 'afl_greek_indicator',
							# 'high_school_gpa',
							'fall_term_gpa',
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
							'total_spring_contact_hrs',
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
							'gini_indx',
							# 'pvrt_rate',
							'median_inc',
							# 'median_value',
							'educ_rate',
							'pct_blk',
							'pct_ai',
							# 'pct_asn',
							'pct_hawi',
							# 'pct_oth',
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
							# 'term_credit_hours',
							# 'total_fall_units',
							'spring_withdrawn_hours',
							# 'athlete',
							'remedial',
							# 'ACAD_PLAN',
							# 'plan_owner_org',
							'business',
							'cahnrs_anml',
							'cahnrs_envr',
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
							'pharmacy',
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
							'unmet_need_ofr'
                            ]].dropna()

pullm_testing_set = pullm_testing_set.reset_index()

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
						# 'distance',
						'pop_dens',
						'underrep_minority', 
						# 'ipeds_ethnic_group_descrshort',
						'pell_eligibility_ind', 
						# 'pell_recipient_ind',
						'first_gen_flag', 
						# 'LSAMP_STEM_Flag',
						# 'anywhere_STEM_Flag',
						# 'honors_program_ind',
						# 'afl_greek_indicator',
						# 'high_school_gpa',
						'fall_term_gpa',
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
						'total_spring_contact_hrs',
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
						'gini_indx',
						# 'pvrt_rate',
						'median_inc',
						# 'median_value',
						'educ_rate',
						'pct_blk',
						'pct_ai',
						# 'pct_asn',
						'pct_hawi',
						# 'pct_oth',
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
						# 'term_credit_hours',
						# 'total_fall_units',
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
						'unmet_need_ofr'
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
							# 'distance',
							'pop_dens',
							'underrep_minority', 
							# 'ipeds_ethnic_group_descrshort',
							'pell_eligibility_ind', 
							# 'pell_recipient_ind',
							'first_gen_flag', 
							# 'LSAMP_STEM_Flag',
							# 'anywhere_STEM_Flag',
							# 'honors_program_ind',
							# 'afl_greek_indicator',
							# 'high_school_gpa',
							'fall_term_gpa',
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
							'total_spring_contact_hrs',
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
							'gini_indx',
							# 'pvrt_rate',
							'median_inc',
							# 'median_value',
							'educ_rate',
							'pct_blk',
							'pct_ai',
							# 'pct_asn',
							'pct_hawi',
							# 'pct_oth',
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
							# 'term_credit_hours',
							# 'total_fall_units',
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
							'unmet_need_ofr'
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
							# 'distance',
							'pop_dens',
							'underrep_minority', 
							# 'ipeds_ethnic_group_descrshort',
							'pell_eligibility_ind', 
							# 'pell_recipient_ind',
							'first_gen_flag', 
							# 'LSAMP_STEM_Flag',
							# 'anywhere_STEM_Flag',
							# 'honors_program_ind',
							# 'afl_greek_indicator',
							# 'high_school_gpa',
							'fall_term_gpa',
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
							'total_spring_contact_hrs',
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
							'gini_indx',
							# 'pvrt_rate',
							'median_inc',
							# 'median_value',
							'educ_rate',
							'pct_blk',
							'pct_ai',
							# 'pct_asn',
							'pct_hawi',
							# 'pct_oth',
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
							# 'term_credit_hours',
							# 'total_fall_units',
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
							'unmet_need_ofr'
                            ]].dropna()

vanco_testing_set = vanco_testing_set.reset_index()

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
						# 'distance',
						'pop_dens',
						'underrep_minority', 
						# 'ipeds_ethnic_group_descrshort',
						'pell_eligibility_ind', 
						# 'pell_recipient_ind',
						'first_gen_flag', 
						# 'LSAMP_STEM_Flag',
						# 'anywhere_STEM_Flag',
						# 'honors_program_ind',
						# 'afl_greek_indicator',
						# 'high_school_gpa',
						'fall_term_gpa',
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
						'total_spring_contact_hrs',
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
						'gini_indx',
						# 'pvrt_rate',
						'median_inc',
						# 'median_value',
						'educ_rate',
						'pct_blk',
						'pct_ai',
						# 'pct_asn',
						'pct_hawi',
						# 'pct_oth',
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
						# 'term_credit_hours',
						# 'total_fall_units',
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
						'unmet_need_ofr'
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
							# 'distance',
							'pop_dens',
							'underrep_minority', 
							# 'ipeds_ethnic_group_descrshort',
							'pell_eligibility_ind', 
							# 'pell_recipient_ind',
							'first_gen_flag', 
							# 'LSAMP_STEM_Flag',
							# 'anywhere_STEM_Flag',
							# 'honors_program_ind',
							# 'afl_greek_indicator',
							# 'high_school_gpa',
							'fall_term_gpa',
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
							'total_spring_contact_hrs',
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
							'gini_indx',
							# 'pvrt_rate',
							'median_inc',
							# 'median_value',
							'educ_rate',
							'pct_blk',
							'pct_ai',
							# 'pct_asn',
							'pct_hawi',
							# 'pct_oth',
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
							# 'term_credit_hours',
							# 'total_fall_units',
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
							'unmet_need_ofr'
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
							# 'distance',
							'pop_dens',
							'underrep_minority', 
							# 'ipeds_ethnic_group_descrshort',
							'pell_eligibility_ind', 
							# 'pell_recipient_ind',
							'first_gen_flag', 
							# 'LSAMP_STEM_Flag',
							# 'anywhere_STEM_Flag',
							# 'honors_program_ind',
							# 'afl_greek_indicator',
							# 'high_school_gpa',
							'fall_term_gpa',
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
							'total_spring_contact_hrs',
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
							'gini_indx',
							# 'pvrt_rate',
							'median_inc',
							# 'median_value',
							'educ_rate',
							'pct_blk',
							'pct_ai',
							# 'pct_asn',
							'pct_hawi',
							# 'pct_oth',
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
							# 'term_credit_hours',
							# 'total_fall_units',
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
							'unmet_need_ofr'
                            ]].dropna()

trici_testing_set = trici_testing_set.reset_index()

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

print('Done\n')

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
						# 'distance',
						'pop_dens',
						'underrep_minority', 
						# 'ipeds_ethnic_group_descrshort',
						'pell_eligibility_ind', 
						# 'pell_recipient_ind',
						'first_gen_flag', 
						# 'LSAMP_STEM_Flag',
						# 'anywhere_STEM_Flag',
						'honors_program_ind',
						# 'afl_greek_indicator',
						# 'high_school_gpa',
						'fall_term_gpa',
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
						'total_spring_contact_hrs',
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
						'gini_indx',
						# 'pvrt_rate',
						'median_inc',
						# 'median_value',
						'educ_rate',
						'pct_blk',
						'pct_ai',
						# 'pct_asn',
						'pct_hawi',
						# 'pct_oth',
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
						# 'term_credit_hours',
						# 'total_fall_units',
						'spring_withdrawn_hours',
						# 'athlete',
						'remedial',
						# 'ACAD_PLAN',
						# 'plan_owner_org',
						'business',
						'cahnrs_anml',
						'cahnrs_envr',
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
						'pharmacy',
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
						'unmet_need_ofr'
                        ]]

pullm_y_train = pullm_training_set['enrl_ind']
# pullm_y_test = pullm_testing_set['enrl_ind']

pullm_tomek_prep = make_column_transformer(
	(StandardScaler(), [
						# 'age',
						# 'min_week_from_term_begin_dt',
						# 'max_week_from_term_begin_dt',
						'count_week_from_term_begin_dt',
						# 'sat_erws',
						# 'sat_mss',
						# 'sat_comp',
						# 'attendee_total_visits',
						# 'distance',
						'pop_dens', 
						# 'qvalue', 
						'median_inc',
						# 'median_value',
						# 'term_credit_hours',
						# 'high_school_gpa',
						'fall_term_gpa',
						# 'spring_midterm_gpa_change',
						# 'awe_instrument',
						# 'cdi_instrument',
						# 'fall_avg_difficulty',
						'spring_avg_difficulty',
						# 'fall_lec_count',
						# 'fall_lab_count',
						# 'fall_lec_contact_hrs',
						# 'fall_lab_contact_hrs',
						'spring_lec_count',
						'spring_lab_count',
						# 'spring_lec_contact_hrs',
						# 'spring_lab_contact_hrs',
						# 'total_fall_contact_hrs',
						'total_spring_contact_hrs',
						# 'fall_midterm_gpa_avg',
						# 'spring_midterm_gpa_avg',
						'cum_adj_transfer_hours',
						# 'term_credit_hours',
						# 'total_fall_units',
						'spring_withdrawn_hours',
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
pullm_x_test = pullm_tomek_prep.fit_transform(pullm_x_test)

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
						# 'distance',
						'pop_dens',
						'underrep_minority', 
						# 'ipeds_ethnic_group_descrshort',
						'pell_eligibility_ind', 
						# 'pell_recipient_ind',
						'first_gen_flag', 
						# 'LSAMP_STEM_Flag',
						# 'anywhere_STEM_Flag',
						# 'honors_program_ind',
						# 'afl_greek_indicator',
						# 'high_school_gpa',
						'fall_term_gpa',
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
						'total_spring_contact_hrs',
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
						'gini_indx',
						# 'pvrt_rate',
						'median_inc',
						# 'median_value',
						'educ_rate',
						'pct_blk',
						'pct_ai',
						# 'pct_asn',
						'pct_hawi',
						# 'pct_oth',
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
						# 'term_credit_hours',
						# 'total_fall_units',
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
						'unmet_need_ofr'
                        ]]

vanco_y_train = vanco_training_set['enrl_ind']
# vanco_y_test = vanco_testing_set['enrl_ind']

vanco_tomek_prep = make_column_transformer(
	(StandardScaler(), [
						# 'age',
						# 'min_week_from_term_begin_dt',
						# 'max_week_from_term_begin_dt',
						'count_week_from_term_begin_dt',
						# 'sat_erws',
						# 'sat_mss',
						# 'sat_comp',
						# 'attendee_total_visits',
						# 'distance',
						'pop_dens', 
						# 'qvalue', 
						'median_inc',
						# 'median_value',
						# 'term_credit_hours',
						# 'high_school_gpa',
						'fall_term_gpa',
						# 'spring_midterm_gpa_change',
						# 'awe_instrument',
						# 'cdi_instrument',
						# 'fall_avg_difficulty',
						'spring_avg_difficulty',
						# 'fall_lec_count',
						# 'fall_lab_count',
						# 'fall_lec_contact_hrs',
						# 'fall_lab_contact_hrs',
						'spring_lec_count',
						'spring_lab_count',
						# 'spring_lec_contact_hrs',
						# 'spring_lab_contact_hrs',
						# 'total_fall_contact_hrs',
						'total_spring_contact_hrs',
						# 'fall_midterm_gpa_avg',
						# 'spring_midterm_gpa_avg',
						'cum_adj_transfer_hours',
						# 'term_credit_hours',
						# 'total_fall_units',
						'spring_withdrawn_hours',
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
vanco_x_test = vanco_tomek_prep.fit_transform(vanco_x_test)

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
						# 'distance',
						'pop_dens',
						'underrep_minority', 
						# 'ipeds_ethnic_group_descrshort',
						'pell_eligibility_ind', 
						# 'pell_recipient_ind',
						'first_gen_flag', 
						# 'LSAMP_STEM_Flag',
						# 'anywhere_STEM_Flag',
						# 'honors_program_ind',
						# 'afl_greek_indicator',
						# 'high_school_gpa',
						'fall_term_gpa',
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
						'total_spring_contact_hrs',
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
						'gini_indx',
						# 'pvrt_rate',
						'median_inc',
						# 'median_value',
						'educ_rate',
						'pct_blk',
						'pct_ai',
						# 'pct_asn',
						'pct_hawi',
						# 'pct_oth',
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
						# 'term_credit_hours',
						# 'total_fall_units',
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
						'unmet_need_ofr'
                        ]]

trici_y_train = trici_training_set['enrl_ind']
# trici_y_test = trici_testing_set['enrl_ind']

trici_tomek_prep = make_column_transformer(
	(StandardScaler(), [
						# 'age',
						# 'min_week_from_term_begin_dt',
						# 'max_week_from_term_begin_dt',
						'count_week_from_term_begin_dt',
						# 'sat_erws',
						# 'sat_mss',
						# 'sat_comp',
						# 'attendee_total_visits',
						# 'distance',
						'pop_dens', 
						# 'qvalue', 
						'median_inc',
						# 'median_value',
						# 'term_credit_hours',
						# 'high_school_gpa',
						'fall_term_gpa',
						# 'spring_midterm_gpa_change',
						# 'awe_instrument',
						# 'cdi_instrument',
						# 'fall_avg_difficulty',
						'spring_avg_difficulty',
						# 'fall_lec_count',
						# 'fall_lab_count',
						# 'fall_lec_contact_hrs',
						# 'fall_lab_contact_hrs',
						'spring_lec_count',
						'spring_lab_count',
						# 'spring_lec_contact_hrs',
						# 'spring_lab_contact_hrs',
						# 'total_fall_contact_hrs',
						'total_spring_contact_hrs',
						# 'fall_midterm_gpa_avg',
						# 'spring_midterm_gpa_avg',
						'cum_adj_transfer_hours',
						# 'term_credit_hours',
						# 'total_fall_units',
						'spring_withdrawn_hours',
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
trici_x_test = trici_tomek_prep.fit_transform(trici_x_test)

trici_under = TomekLinks(sampling_strategy='all', n_jobs=-1)
trici_x_train, trici_y_train = trici_under.fit_resample(trici_x_train, trici_y_train)

trici_tomek_index = trici_under.sample_indices_
trici_training_set = trici_training_set.reset_index(drop=True)

trici_tomek_set = trici_training_set.drop(trici_tomek_index)
trici_tomek_set.to_csv('Z:\\Nathan\\Models\\student_risk\\outliers\\trici_frsh_tomek_set.csv', encoding='utf-8', index=False)

print('Done\n')

#%%
# Standard logistic model

# Pullman standard model
print('\nStandard logistic model for Pullman freshmen...\n')

pullm_y, pullm_x = dmatrices('enrl_ind ~ pop_dens + educ_rate \
				+ male + underrep_minority \
				+ pct_blk + pct_ai + pct_hawi + pct_two + pct_hisp \
                + pell_eligibility_ind + honors_program_ind \
				+ AD_DTA + AD_AST + AP + RS + CHS + IB_AICE \
				+ business + comm + education + medicine + nursing + pharmacy + vet_med \
				+ cahnrs_anml + cahnrs_envr + cahnrs_econ + cahnrext \
				+ cas_chem + cas_crim + cas_math + cas_psyc + cas_biol + cas_engl + cas_phys + cas \
                + vcea_bioe + vcea_cive + vcea_desn + vcea_eecs + vcea_mech + vcea \
                + first_gen_flag \
				+ spring_avg_difficulty + spring_avg_pct_CDF + spring_avg_pct_withdrawn \
				+ spring_lec_count + spring_lab_count \
				+ total_spring_contact_hrs \
				+ spring_withdrawn_hours \
                + resident + gini_indx + median_inc \
            	+ fall_term_gpa \
				+ remedial \
				+ cum_adj_transfer_hours \
				+ parent1_highest_educ_lvl + parent2_highest_educ_lvl \
            	+ unmet_need_ofr \
				+ count_week_from_term_begin_dt', data=pullm_logit_df, return_type='dataframe')

pullm_logit_mod = Logit(pullm_y, pullm_x)
pullm_logit_res = pullm_logit_mod.fit(maxiter=500)
print(pullm_logit_res.summary())

print('\n')

#%%
# Vancouver standard model
print('\nStandard logistic model for Vancouver freshmen...\n')

vanco_y, vanco_x = dmatrices('enrl_ind ~ pop_dens + educ_rate \
				+ male + underrep_minority \
				+ pct_blk + pct_ai + pct_hawi + pct_two + pct_hisp \
                + pell_eligibility_ind \
                + first_gen_flag \
				+ spring_avg_difficulty + spring_avg_pct_CDF + spring_avg_pct_withdrawn \
				+ spring_lec_count + spring_lab_count \
				+ total_spring_contact_hrs \
				+ spring_withdrawn_hours \
                + resident + gini_indx + median_inc \
            	+ fall_term_gpa \
				+ remedial \
				+ cum_adj_transfer_hours \
				+ parent1_highest_educ_lvl + parent2_highest_educ_lvl \
            	+ unmet_need_ofr \
				+ count_week_from_term_begin_dt', data=vanco_logit_df, return_type='dataframe')

vanco_logit_mod = Logit(vanco_y, vanco_x)
vanco_logit_res = vanco_logit_mod.fit(maxiter=500)
print(vanco_logit_res.summary())

print('\n')

#%%
# Tri-Cities standard model
print('\nStandard logistic model for Tri-Cities freshmen...\n')

trici_y, trici_x = dmatrices('enrl_ind ~ pop_dens + educ_rate \
				+ male + underrep_minority \
				+ pct_blk + pct_ai + pct_hawi + pct_two + pct_hisp \
                + pell_eligibility_ind \
                + first_gen_flag \
				+ spring_avg_difficulty + spring_avg_pct_CDF + spring_avg_pct_withdrawn \
				+ spring_lec_count + spring_lab_count \
				+ total_spring_contact_hrs \
				+ spring_withdrawn_hours \
                + resident + gini_indx + median_inc \
            	+ fall_term_gpa \
				+ remedial \
				+ cum_adj_transfer_hours \
				+ parent1_highest_educ_lvl + parent2_highest_educ_lvl \
            	+ unmet_need_ofr \
				+ count_week_from_term_begin_dt', data=trici_logit_df, return_type='dataframe')

trici_logit_mod = Logit(trici_y, trici_x)
trici_logit_res = trici_logit_mod.fit(maxiter=500)
print(trici_logit_res.summary())

print('\n')

#%%
# VIF diagnostic

# Pullman VIF
print('VIF for Pullman...\n')
pullm_vif = pd.DataFrame()
pullm_vif['vif factor'] = [variance_inflation_factor(pullm_x.values, i) for i in range(pullm_x.shape[1])]
pullm_vif['features'] = pullm_x.columns
pullm_vif = pullm_vif.sort_values(by=['vif factor'], ascending=False, inplace=True, ignore_index=True)
print(pullm_vif.round(1).to_string())
print('\n')

#%%
# Vancouver VIF
print('VIF for Vancouver...\n')
vanco_vif = pd.DataFrame()
vanco_vif['vif factor'] = [variance_inflation_factor(vanco_x.values, i) for i in range(vanco_x.shape[1])]
vanco_vif['features'] = vanco_x.columns
vanco_vif = vanco_vif.sort_values(by=['vif factor'], ascending=False, inplace=True, ignore_index=True)
print(vanco_vif.round(1).to_string())
print('\n')

#%%
# Tri-Cities VIF
print('VIF for Tri-Cities...\n')
trici_vif = pd.DataFrame()
trici_vif['vif factor'] = [variance_inflation_factor(trici_x.values, i) for i in range(trici_x.shape[1])]
trici_vif['features'] = trici_x.columns
trici_vif = trici_vif.sort_values(by=['vif factor'], ascending=False, inplace=True, ignore_index=True)
print(trici_vif.round(1).to_string())
print('\n')

#%%
print('Run machine learning models for freshmen...\n')

# Logistic model

# Pullman logistic
pullm_lreg = LogisticRegression(penalty='elasticnet', class_weight='balanced', solver='saga', max_iter=2000, l1_ratio=0.0, C=1.0, n_jobs=-1, verbose=False).fit(pullm_x_train, pullm_y_train)

pullm_lreg_probs = pullm_lreg.predict_proba(pullm_x_train)
pullm_lreg_probs = pullm_lreg_probs[:, 1]
pullm_lreg_auc = roc_auc_score(pullm_y_train, pullm_lreg_probs)

print(f'\nOverall accuracy for Pullman logistic model (training): {pullm_lreg.score(pullm_x_train, pullm_y_train):.4f}')
print(f'ROC AUC for Pullman logistic model (training): {pullm_lreg_auc:.4f}\n')

pullm_lreg_fpr, pullm_lreg_tpr, pullm_thresholds = roc_curve(pullm_y_train, pullm_lreg_probs, drop_intermediate=False)

#%%
# Vancouver logistic
vanco_lreg = LogisticRegression(penalty='elasticnet', class_weight='balanced', solver='saga', max_iter=2000, l1_ratio=0.0, C=1.0, n_jobs=-1, verbose=False).fit(vanco_x_train, vanco_y_train)

vanco_lreg_probs = vanco_lreg.predict_proba(vanco_x_train)
vanco_lreg_probs = vanco_lreg_probs[:, 1]
vanco_lreg_auc = roc_auc_score(vanco_y_train, vanco_lreg_probs)

print(f'\nOverall accuracy for Vancouver logistic model (training): {vanco_lreg.score(vanco_x_train, vanco_y_train):.4f}')
print(f'ROC AUC for Vancouver logistic model (training): {vanco_lreg_auc:.4f}\n')

vanco_lreg_fpr, vanco_lreg_tpr, vanco_thresholds = roc_curve(vanco_y_train, vanco_lreg_probs, drop_intermediate=False)

#%%
# Tri-Cities logistic
trici_lreg = LogisticRegression(penalty='elasticnet', class_weight='balanced', solver='saga', max_iter=2000, l1_ratio=0.0, C=1.0, n_jobs=-1, verbose=False).fit(trici_x_train, trici_y_train)

trici_lreg_probs = trici_lreg.predict_proba(trici_x_train)
trici_lreg_probs = trici_lreg_probs[:, 1]
trici_lreg_auc = roc_auc_score(trici_y_train, trici_lreg_probs)

print(f'\nOverall accuracy for Tri-Cities logistic model (training): {trici_lreg.score(trici_x_train, trici_y_train):.4f}')
print(f'ROC AUC for Tri-Cities logistic model (training): {trici_lreg_auc:.4f}\n')

trici_lreg_fpr, trici_lreg_tpr, trici_thresholds = roc_curve(trici_y_train, trici_lreg_probs, drop_intermediate=False)

#%%
# Stochastic gradient descent model

# Pullman SGD
pullm_sgd = SGDClassifier(loss='modified_huber', penalty='elasticnet', class_weight='balanced', early_stopping=False, max_iter=2000, l1_ratio=0.0, learning_rate='adaptive', eta0=0.0001, tol=0.0001, n_iter_no_change=100, n_jobs=-1, verbose=False).fit(pullm_x_train, pullm_y_train)

pullm_sgd_probs = pullm_sgd.predict_proba(pullm_x_train)
pullm_sgd_probs = pullm_sgd_probs[:, 1]
pullm_sgd_auc = roc_auc_score(pullm_y_train, pullm_sgd_probs)

print(f'\nOverall accuracy for Pullman SGD model (training): {pullm_sgd.score(pullm_x_train, pullm_y_train):.4f}')
print(f'ROC AUC for Pullman SGD model (training): {pullm_sgd_auc:.4f}\n')

pullm_sgd_fpr, pullm_sgd_tpr, pullm_thresholds = roc_curve(pullm_y_train, pullm_sgd_probs, drop_intermediate=False)

#%%
# Vancouver SGD
vanco_sgd = SGDClassifier(loss='modified_huber', penalty='elasticnet', class_weight='balanced', early_stopping=False, max_iter=2000, l1_ratio=0.0, learning_rate='adaptive', eta0=0.0001, tol=0.0001, n_iter_no_change=100, n_jobs=-1, verbose=False).fit(vanco_x_train, vanco_y_train)

vanco_sgd_probs = vanco_sgd.predict_proba(vanco_x_train)
vanco_sgd_probs = vanco_sgd_probs[:, 1]
vanco_sgd_auc = roc_auc_score(vanco_y_train, vanco_sgd_probs)

print(f'\nOverall accuracy for Vancouver SGD model (training): {vanco_sgd.score(vanco_x_train, vanco_y_train):.4f}')
print(f'ROC AUC for Vancouver SGD model (training): {vanco_sgd_auc:.4f}\n')

vanco_sgd_fpr, vanco_sgd_tpr, vanco_thresholds = roc_curve(vanco_y_train, vanco_sgd_probs, drop_intermediate=False)

#%%
# Tri-Cities SGD
trici_sgd = SGDClassifier(loss='modified_huber', penalty='elasticnet', class_weight='balanced', early_stopping=False, max_iter=2000, l1_ratio=0.0, learning_rate='adaptive', eta0=0.0001, tol=0.0001, n_iter_no_change=100, n_jobs=-1, verbose=False).fit(trici_x_train, trici_y_train)

trici_sgd_probs = trici_sgd.predict_proba(trici_x_train)
trici_sgd_probs = trici_sgd_probs[:, 1]
trici_sgd_auc = roc_auc_score(trici_y_train, trici_sgd_probs)

print(f'\nOverall accuracy for Tri-Cities SGD model (training): {trici_sgd.score(trici_x_train, trici_y_train):.4f}')
print(f'ROC AUC for Tri-Cities SGD model (training): {trici_sgd_auc:.4f}\n')

trici_sgd_fpr, trici_sgd_tpr, trici_thresholds = roc_curve(trici_y_train, trici_sgd_probs, drop_intermediate=False)

#%%
# Multi-layer perceptron model

# Pullman MLP
# pullm_mlp = MLPClassifier(hidden_layer_sizes=(75,50,25), activation='relu', solver='sgd', alpha=2.5, learning_rate_init=0.001, n_iter_no_change=25, max_iter=2000, verbose=False).fit(pullm_x_train, pullm_y_train)

# pullm_mlp_probs = pullm_mlp.predict_proba(pullm_x_train)
# pullm_mlp_probs = pullm_mlp_probs[:, 1]
# pullm_mlp_auc = roc_auc_score(pullm_y_train, pullm_mlp_probs)

# print(f'\nOverall accuracy for multi-layer perceptron model (training): {pullm_mlp.score(pullm_x_train, pullm_y_train):.4f}')
# print(f'ROC AUC for multi-layer perceptron model (training): {pullm_mlp_auc:.4f}\n')

# mlp_fpr, mlp_tpr, thresholds = roc_curve(pullm_y_train, pullm_mlp_probs, drop_intermediate=False)

#%%
# Vancouver MLP
# vanco_mlp = MLPClassifier(hidden_layer_sizes=(75,50,25), activation='relu', solver='sgd', alpha=2.5, learning_rate_init=0.001, n_iter_no_change=25, max_iter=2000, verbose=False).fit(vanco_x_train, vanco_y_train)

# vanco_mlp_probs = vanco_mlp.predict_proba(vanco_x_train)
# vanco_mlp_probs = vanco_mlp_probs[:, 1]
# vanco_mlp_auc = roc_auc_score(vanco_y_train, vanco_mlp_probs)

# print(f'\nOverall accuracy for multi-layer perceptron model (training): {vanco_mlp.score(vanco_x_train, vanco_y_train):.4f}')
# print(f'ROC AUC for multi-layer perceptron model (training): {vanco_mlp_auc:.4f}\n')

# mlp_fpr, mlp_tpr, thresholds = roc_curve(vanco_y_train, vanco_mlp_probs, drop_intermediate=False)

#%%
# Tri-Cities MLP
# trici_mlp = MLPClassifier(hidden_layer_sizes=(75,50,25), activation='relu', solver='sgd', alpha=2.5, learning_rate_init=0.001, n_iter_no_change=25, max_iter=2000, verbose=False).fit(trici_x_train, trici_y_train)

# trici_mlp_probs = trici_mlp.predict_proba(trici_x_train)
# trici_mlp_probs = trici_mlp_probs[:, 1]
# trici_mlp_auc = roc_auc_score(trici_y_train, trici_mlp_probs)

# print(f'\nOverall accuracy for multi-layer perceptron model (training): {trici_mlp.score(trici_x_train, trici_y_train):.4f}')
# print(f'ROC AUC for multi-layer perceptron model (training): {trici_mlp_auc:.4f}\n')

# mlp_fpr, mlp_tpr, thresholds = roc_curve(trici_y_train, trici_mlp_probs, drop_intermediate=False)

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
# Prepare model predictions
print('Prepare model predictions...')

# Pullman probabilites
pullm_lreg_pred_probs = pullm_lreg.predict_proba(pullm_x_test)
pullm_lreg_pred_probs = pullm_lreg_pred_probs[:, 1]
pullm_sgd_pred_probs = pullm_sgd.predict_proba(pullm_x_test)
pullm_sgd_pred_probs = pullm_sgd_pred_probs[:, 1]
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
# trici_mlp_pred_probs = trici_mlp.predict_proba(trici_x_test)
# trici_mlp_pred_probs = trici_mlp_pred_probs[:, 1]
trici_vcf_pred_probs = trici_vcf.predict_proba(trici_x_test)
trici_vcf_pred_probs = trici_vcf_pred_probs[:, 1]

print('Done\n')

#%%
# Output model predictions to file
print('Output model predictions and model...')

# Pullman predicted outcome
pullm_pred_outcome['lr_prob'] = pd.DataFrame(pullm_lreg_pred_probs)
pullm_pred_outcome['lr_pred'] = pullm_lreg.predict(pullm_x_test)
pullm_pred_outcome['sgd_prob'] = pd.DataFrame(pullm_sgd_pred_probs)
pullm_pred_outcome['sgd_pred'] = pullm_sgd.predict(pullm_x_test)
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
# trici_pred_outcome['mlp_prob'] = pd.DataFrame(trici_mlp_pred_probs)
# trici_pred_outcome['mlp_pred'] = trici_mlp.predict(trici_x_test)
trici_pred_outcome['vcf_prob'] = pd.DataFrame(trici_vcf_pred_probs)
trici_pred_outcome['vcf_pred'] = trici_vcf.predict(trici_x_test)
trici_pred_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\trici\\trici_frsh_pred_outcome.csv', encoding='utf-8', index=False)

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
# Pullman current outcome
pullm_current_outcome['emplid'] = pullm_current_outcome['emplid'].astype(str).str.zfill(9)
pullm_current_outcome['risk_prob'] = 1 - pd.DataFrame(pullm_vcf_pred_probs).round(4)

pullm_current_outcome['date'] = date.today()
pullm_current_outcome['model_id'] = 5

#%%
# Vancouver current outcome
vanco_current_outcome['emplid'] = vanco_current_outcome['emplid'].astype(str).str.zfill(9)
vanco_current_outcome['risk_prob'] = 1 - pd.DataFrame(vanco_vcf_pred_probs).round(4)

vanco_current_outcome['date'] = date.today()
vanco_current_outcome['model_id'] = 5

#%%
# Tri-Cities current outcome
trici_current_outcome['emplid'] = trici_current_outcome['emplid'].astype(str).str.zfill(9)
trici_current_outcome['risk_prob'] = 1 - pd.DataFrame(trici_vcf_pred_probs).round(4)

trici_current_outcome['date'] = date.today()
trici_current_outcome['model_id'] = 5

#%%
# Pullman to csv and to sql
if not os.path.isfile('Z:\\Nathan\\Models\\student_risk\\predictions\\pullm_student_outcome.csv'):
	pullm_current_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\pullm_student_outcome.csv', encoding='utf-8', index=False)
	pullm_current_outcome.to_sql('student_outcome', con=auto_engine, if_exists='append', index=False, schema='oracle_int.dbo')
else:
	pullm_prior_outcome = pd.read_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\pullm_student_outcome.csv', encoding='utf-8', low_memory=False)
	pullm_prior_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\pullm_student_backup.csv', encoding='utf-8', index=False)
	pullm_student_outcome = pd.concat([pullm_prior_outcome, pullm_current_outcome])
	pullm_student_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\pullm_student_outcome.csv', encoding='utf-8', index=False)
	pullm_current_outcome.to_sql('student_outcome', con=auto_engine, if_exists='append', index=False, schema='oracle_int.dbo')

#%%
# Vancouver to csv and to sql
# if not os.path.isfile('Z:\\Nathan\\Models\\student_risk\\predictions\\vanco_student_outcome.csv'):
# 	vanco_current_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\vanco_student_outcome.csv', encoding='utf-8', index=False)
# 	vanco_current_outcome.to_sql('student_outcome', con=auto_engine, if_exists='append', index=False, schema='oracle_int.dbo')
# else:
# 	vanco_prior_outcome = pd.read_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\vanco_student_outcome.csv', encoding='utf-8', low_memory=False)
# 	vanco_prior_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\vanco_student_backup.csv', encoding='utf-8', index=False)
# 	vanco_student_outcome = pd.concat([vanco_prior_outcome, vanco_current_outcome])
# 	vanco_student_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\vanco_student_outcome.csv', encoding='utf-8', index=False)
# 	vanco_current_outcome.to_sql('student_outcome', con=auto_engine, if_exists='append', index=False, schema='oracle_int.dbo')

#%%
# Tri-Cities to csv and to sql
# if not os.path.isfile('Z:\\Nathan\\Models\\student_risk\\predictions\\trici_student_outcome.csv'):
# 	trici_current_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\trici_student_outcome.csv', encoding='utf-8', index=False)
# 	trici_current_outcome.to_sql('student_outcome', con=auto_engine, if_exists='append', index=False, schema='oracle_int.dbo')
# else:
# 	trici_prior_outcome = pd.read_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\trici_student_outcome.csv', encoding='utf-8', low_memory=False)
# 	trici_prior_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\trici_student_backup.csv', encoding='utf-8', index=False)
# 	trici_student_outcome = pd.concat([trici_prior_outcome, trici_current_outcome])
# 	trici_student_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\predictions\\trici_student_outcome.csv', encoding='utf-8', index=False)
# 	trici_current_outcome.to_sql('student_outcome', con=auto_engine, if_exists='append', index=False, schema='oracle_int.dbo')

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

print('Done\n')
