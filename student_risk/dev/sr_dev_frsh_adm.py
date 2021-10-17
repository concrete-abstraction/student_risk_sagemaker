#%%
from student_risk import builder
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import statsmodels.graphics.api as smg
from imblearn.under_sampling import TomekLinks
from matplotlib.legend_handler import HandlerLine2D
from patsy import dmatrices
from sklearn.compose import make_column_transformer
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import MinMaxScaler, StandardScaler, OneHotEncoder
from sklearn.linear_model import LinearRegression, LogisticRegression, SGDClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.ensemble import VotingClassifier
from sklearn.metrics import confusion_matrix, roc_curve, roc_auc_score
from sklearn.model_selection import GridSearchCV
from statsmodels.api import OLS
from statsmodels.discrete.discrete_model import Logit
from statsmodels.stats.outliers_influence import variance_inflation_factor

#%%
# Global variables
wsu_color = (0.596,0.117,0.196)
wsu_cmap = sns.light_palette("#981e32",as_cmap=True)

#%%
# SAS dataset builder
builder.DatasetBuilder.build_admissions_dev()

#%%
# Import pre-split data
training_set = pd.read_csv('Z:\\Nathan\\Models\\student_risk\\datasets\\training_set.csv', encoding='utf-8', low_memory=False)
testing_set = pd.read_csv('Z:\\Nathan\\Models\\student_risk\\datasets\\testing_set.csv', encoding='utf-8', low_memory=False)

#%%
# Training AWE instrumental variable
training_awe = training_set[[
                            'emplid',
                            'high_school_gpa',
                            'underrep_minority',
                            'male',
                            'sat_erws',
                            'sat_mss',
                            'educ_rate',
                            'gini_indx',
                            'median_inc'                
                            ]].dropna()

awe_x_train = training_awe[[
                            'sat_erws',
                            'sat_mss',
                            'underrep_minority',
                            'male',
                            'educ_rate',
                            'gini_indx',
                            'median_inc'
                            ]]

awe_y_train = training_awe[[
                            'high_school_gpa'
                            ]]

y, x = dmatrices('high_school_gpa ~ sat_erws + sat_mss + underrep_minority + male + educ_rate + gini_indx + median_inc', data=training_awe, return_type='dataframe')
reg_mod = OLS(y, x)
reg_res = reg_mod.fit()
print(reg_res.summary())

reg = LinearRegression()
reg.fit(awe_x_train, awe_y_train)

training_awe_pred = pd.DataFrame()
training_awe_pred['emplid'] = training_awe['emplid']
training_awe_pred['actual'] = training_awe['high_school_gpa']
training_awe_pred['predicted'] = reg.predict(awe_x_train)
training_awe_pred['awe_instrument'] = training_awe_pred['actual'] - training_awe_pred['predicted']

training_set = training_set.join(training_awe_pred.set_index('emplid'), on='emplid')

#%%
# Testing AWE instrumental variable
testing_awe = testing_set[[
                            'emplid',
                            'high_school_gpa',
                            'underrep_minority',
                            'male',
                            'sat_erws',
                            'sat_mss',
                            'educ_rate',
                            'gini_indx',
                            'median_inc'
                            ]].dropna()

awe_x_test = testing_awe[[
                            'sat_erws',
                            'sat_mss',
                            'underrep_minority',
                            'male',
                            'educ_rate',
                            'gini_indx',
                            'median_inc'                        
                            ]]

awe_y_test = testing_awe[[
                            'high_school_gpa'
                            ]]

y, x = dmatrices('high_school_gpa ~ sat_erws + sat_mss + underrep_minority + male + educ_rate + gini_indx + median_inc', data=testing_awe, return_type='dataframe')
reg_mod = OLS(y, x)
reg_res = reg_mod.fit()
print(reg_res.summary())

reg = LinearRegression()
reg.fit(awe_x_test, awe_y_test)

testing_awe_pred = pd.DataFrame()
testing_awe_pred['emplid'] = testing_awe['emplid']
testing_awe_pred['awe_actual'] = testing_awe['high_school_gpa']
testing_awe_pred['awe_predicted'] = reg.predict(awe_x_test)
testing_awe_pred['awe_instrument'] = testing_awe_pred['awe_actual'] - testing_awe_pred['awe_predicted']

testing_set = testing_set.join(testing_awe_pred.set_index('emplid'), on='emplid')

#%%
# Training CDI instrumental variable
training_cdi = training_set[[
                            'emplid',
                            'high_school_gpa',
                            'class_count',
                            'sat_erws',
                            'sat_mss',
                            'underrep_minority',
                            'male',
                            'median_inc',
                            'avg_pct_withdrawn',
                            'avg_difficulty'                
                            ]].dropna()

cdi_x_train = training_cdi[[
                            'high_school_gpa',
                            'class_count',
                            'sat_erws',
                            'sat_mss',
                            'underrep_minority',
                            'male',
                            'median_inc',
                            'avg_pct_withdrawn'
                            ]]

cdi_y_train = training_cdi[[
                            'avg_difficulty'
                            ]]

y, x = dmatrices('avg_difficulty ~ high_school_gpa + class_count + avg_pct_withdrawn + sat_erws + sat_mss + underrep_minority + male + median_inc', data=training_cdi, return_type='dataframe')
reg_mod = OLS(y, x)
reg_res = reg_mod.fit()
print(reg_res.summary())

reg = LinearRegression()
reg.fit(cdi_x_train, cdi_y_train)

training_cdi_pred = pd.DataFrame()
training_cdi_pred['emplid'] = training_cdi['emplid']
training_cdi_pred['cdi_actual'] = training_cdi['avg_difficulty']
training_cdi_pred['cdi_predicted'] = reg.predict(cdi_x_train)
training_cdi_pred['cdi_instrument'] = training_cdi_pred['cdi_actual'] - training_cdi_pred['cdi_predicted']

training_set = training_set.join(training_cdi_pred.set_index('emplid'), on='emplid')

#%%
# Testing CDI instrumental variable
testing_cdi = testing_set[[
                            'emplid',
                            'high_school_gpa',
                            'class_count',
                            'sat_erws',
                            'sat_mss',
                            'underrep_minority',
                            'male',
                            'median_inc',
                            'avg_pct_withdrawn',
                            'avg_difficulty'                
                            ]].dropna()

cdi_x_test = testing_cdi[[
                            'high_school_gpa',
                            'class_count',
                            'sat_erws',
                            'sat_mss',
                            'underrep_minority',
                            'male',
                            'median_inc',
                            'avg_pct_withdrawn' 
                            ]]

cdi_y_test = testing_cdi[[
                            'avg_difficulty'
                            ]]

y, x = dmatrices('avg_difficulty ~ high_school_gpa + class_count + avg_pct_withdrawn + sat_erws + sat_mss + underrep_minority + male + median_inc', data=testing_cdi, return_type='dataframe')
reg_mod = OLS(y, x)
reg_res = reg_mod.fit()
print(reg_res.summary())

reg = LinearRegression()
reg.fit(cdi_x_test, cdi_y_test)

testing_cdi_pred = pd.DataFrame()
testing_cdi_pred['emplid'] = testing_cdi['emplid']
testing_cdi_pred['cdi_actual'] = testing_cdi['avg_difficulty']
testing_cdi_pred['cdi_predicted'] = reg.predict(cdi_x_test)
testing_cdi_pred['cdi_instrument'] = testing_cdi_pred['cdi_actual'] - testing_cdi_pred['cdi_predicted']

testing_set = testing_set.join(testing_cdi_pred.set_index('emplid'), on='emplid')

#%%
# Prepare dataframes

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
						'min_week_from_term_begin_dt',
						# 'max_week_from_term_begin_dt',
						# 'count_week_from_term_begin_dt',
						# 'marital_status',
						'distance',
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
						'high_school_gpa',
						# 'fall_cum_gpa',
						# 'spring_midterm_gpa_change',
						# 'awe_instrument',
						# 'cdi_instrument',
						'fall_avg_difficulty',
						'fall_avg_pct_withdrawn',
						# 'fall_avg_pct_CDFW',
						'fall_avg_pct_CDF',
						# 'fall_avg_pct_DFW',
						# 'fall_avg_pct_DF',
						# 'spring_avg_difficulty',
						# 'spring_avg_pct_withdrawn',
						# 'spring_avg_pct_CDFW',
						# 'spring_avg_pct_CDF',
						# 'spring_avg_pct_DFW',
						# 'spring_avg_pct_DF',
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
						# 'fall_midterm_gpa_avg',
						# 'fall_midterm_gpa_avg_ind',
						# 'spring_midterm_gpa_avg',
						# 'spring_midterm_gpa_avg_ind',
						# 'cum_adj_transfer_hours',
						'resident',
						# 'father_wsu_flag',
						# 'mother_wsu_flag',
						'parent1_highest_educ_lvl',
						'parent2_highest_educ_lvl',
						# 'citizenship_country',
						'gini_indx',
						'pvrt_rate',
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
						# 'total_fall_units',
						# 'term_withdrawn_hours',
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
							'min_week_from_term_begin_dt',
							# 'max_week_from_term_begin_dt',
							# 'count_week_from_term_begin_dt',
							# 'marital_status',
							'distance',
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
							'high_school_gpa',
							# 'fall_cum_gpa',
							# 'spring_midterm_gpa_change',
							# 'awe_instrument',
							# 'cdi_instrument',
							'fall_avg_difficulty',
							'fall_avg_pct_withdrawn',
							# 'fall_avg_pct_CDFW',
							'fall_avg_pct_CDF',
							# 'fall_avg_pct_DFW',
							# 'fall_avg_pct_DF',
							# 'spring_avg_difficulty',
							# 'spring_avg_pct_withdrawn',
							# 'spring_avg_pct_CDFW',
							# 'spring_avg_pct_CDF',
							# 'spring_avg_pct_DFW',
							# 'spring_avg_pct_DF',
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
							# 'fall_midterm_gpa_avg',
							# 'fall_midterm_gpa_avg_ind',
							# 'spring_midterm_gpa_avg',
							# 'spring_midterm_gpa_avg_ind',
							# 'cum_adj_transfer_hours',
							'resident',
							# 'father_wsu_flag',
							# 'mother_wsu_flag',
							'parent1_highest_educ_lvl',
							'parent2_highest_educ_lvl',
							# 'citizenship_country',
							'gini_indx',
							'pvrt_rate',
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
							# 'total_fall_units',
							# 'term_withdrawn_hours',
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

pullm_testing_set = testing_set[(testing_set['adj_acad_prog_primary_campus'] == 'PULLM') & (testing_set['adj_admit_type_cat'] == 'FRSH')][[
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
							'min_week_from_term_begin_dt',
							# 'max_week_from_term_begin_dt',
							# 'count_week_from_term_begin_dt',
							# 'marital_status',
							'distance',
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
							'high_school_gpa',
							# 'fall_cum_gpa',
							# 'spring_midterm_gpa_change',
							# 'awe_instrument',
							# 'cdi_instrument',
							'fall_avg_difficulty',
							'fall_avg_pct_withdrawn',
							# 'fall_avg_pct_CDFW',
							'fall_avg_pct_CDF',
							# 'fall_avg_pct_DFW',
							# 'fall_avg_pct_DF',
							# 'spring_avg_difficulty',
							# 'spring_avg_pct_withdrawn',
							# 'spring_avg_pct_CDFW',
							# 'spring_avg_pct_CDF',
							# 'spring_avg_pct_DFW',
							# 'spring_avg_pct_DF',
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
							# 'fall_midterm_gpa_avg',
							# 'fall_midterm_gpa_avg_ind',
							# 'spring_midterm_gpa_avg',
							# 'spring_midterm_gpa_avg_ind',
							# 'cum_adj_transfer_hours',
							'resident',
							# 'father_wsu_flag',
							# 'mother_wsu_flag',
							'parent1_highest_educ_lvl',
							'parent2_highest_educ_lvl',
							# 'citizenship_country',
							'gini_indx',
							'pvrt_rate',
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
							# 'total_fall_units',
							# 'term_withdrawn_hours',
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

pullm_testing_set = pullm_testing_set.reset_index()

pullm_pred_outcome = pullm_testing_set[[ 
                            'emplid',
                            'enrl_ind'
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
						'min_week_from_term_begin_dt',
						# 'max_week_from_term_begin_dt',
						# 'count_week_from_term_begin_dt',
						# 'marital_status',
						'distance',
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
						'high_school_gpa',
						# 'fall_cum_gpa',
						# 'spring_midterm_gpa_change',
						# 'awe_instrument',
						# 'cdi_instrument',
						'fall_avg_difficulty',
						'fall_avg_pct_withdrawn',
						# 'fall_avg_pct_CDFW',
						'fall_avg_pct_CDF',
						# 'fall_avg_pct_DFW',
						# 'fall_avg_pct_DF',
						# 'spring_avg_difficulty',
						# 'spring_avg_pct_withdrawn',
						# 'spring_avg_pct_CDFW',
						# 'spring_avg_pct_CDF',
						# 'spring_avg_pct_DFW',
						# 'spring_avg_pct_DF',
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
						# 'fall_midterm_gpa_avg',
						# 'fall_midterm_gpa_avg_ind',
						# 'spring_midterm_gpa_avg',
						# 'spring_midterm_gpa_avg_ind',
						# 'cum_adj_transfer_hours',
						'resident',
						# 'father_wsu_flag',
						# 'mother_wsu_flag',
						'parent1_highest_educ_lvl',
						'parent2_highest_educ_lvl',
						# 'citizenship_country',
						'gini_indx',
						'pvrt_rate',
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
						# 'term_withdrawn_hours',
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
							'min_week_from_term_begin_dt',
							# 'max_week_from_term_begin_dt',
							# 'count_week_from_term_begin_dt',
							# 'marital_status',
							'distance',
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
							'high_school_gpa',
							# 'fall_cum_gpa',
							# 'spring_midterm_gpa_change',
							# 'awe_instrument',
							# 'cdi_instrument',
							'fall_avg_difficulty',
							'fall_avg_pct_withdrawn',
							# 'fall_avg_pct_CDFW',
							'fall_avg_pct_CDF',
							# 'fall_avg_pct_DFW',
							# 'fall_avg_pct_DF',
							# 'spring_avg_difficulty',
							# 'spring_avg_pct_withdrawn',
							# 'spring_avg_pct_CDFW',
							# 'spring_avg_pct_CDF',
							# 'spring_avg_pct_DFW',
							# 'spring_avg_pct_DF',
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
							# 'fall_midterm_gpa_avg',
							# 'fall_midterm_gpa_avg_ind',
							# 'spring_midterm_gpa_avg',
							# 'spring_midterm_gpa_avg_ind',
							# 'cum_adj_transfer_hours',
							'resident',
							# 'father_wsu_flag',
							# 'mother_wsu_flag',
							'parent1_highest_educ_lvl',
							'parent2_highest_educ_lvl',
							# 'citizenship_country',
							'gini_indx',
							'pvrt_rate',
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
							# 'term_withdrawn_hours',
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

vanco_testing_set = testing_set[(testing_set['campus'] == 'VANCO') & (testing_set['adj_admit_type_cat'] == 'FRSH')][[
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
							'min_week_from_term_begin_dt',
							# 'max_week_from_term_begin_dt',
							# 'count_week_from_term_begin_dt',
							# 'marital_status',
							'distance',
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
							'high_school_gpa',
							# 'fall_cum_gpa',
							# 'spring_midterm_gpa_change',
							# 'awe_instrument',
							# 'cdi_instrument',
							'fall_avg_difficulty',
							'fall_avg_pct_withdrawn',
							# 'fall_avg_pct_CDFW',
							'fall_avg_pct_CDF',
							# 'fall_avg_pct_DFW',
							# 'fall_avg_pct_DF',
							# 'spring_avg_difficulty',
							# 'spring_avg_pct_withdrawn',
							# 'spring_avg_pct_CDFW',
							# 'spring_avg_pct_CDF',
							# 'spring_avg_pct_DFW',
							# 'spring_avg_pct_DF',
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
							# 'fall_midterm_gpa_avg',
							# 'fall_midterm_gpa_avg_ind',
							# 'spring_midterm_gpa_avg',
							# 'spring_midterm_gpa_avg_ind',
							# 'cum_adj_transfer_hours',
							'resident',
							# 'father_wsu_flag',
							# 'mother_wsu_flag',
							'parent1_highest_educ_lvl',
							'parent2_highest_educ_lvl',
							# 'citizenship_country',
							'gini_indx',
							'pvrt_rate',
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
							# 'term_withdrawn_hours',
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
                            'emplid'
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
						'min_week_from_term_begin_dt',
						# 'max_week_from_term_begin_dt',
						# 'count_week_from_term_begin_dt',
						# 'marital_status',
						'distance',
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
						'high_school_gpa',
						# 'fall_cum_gpa',
						# 'spring_midterm_gpa_change',
						# 'awe_instrument',
						# 'cdi_instrument',
						'fall_avg_difficulty',
						'fall_avg_pct_withdrawn',
						# 'fall_avg_pct_CDFW',
						'fall_avg_pct_CDF',
						# 'fall_avg_pct_DFW',
						# 'fall_avg_pct_DF',
						# 'spring_avg_difficulty',
						# 'spring_avg_pct_withdrawn',
						# 'spring_avg_pct_CDFW',
						# 'spring_avg_pct_CDF',
						# 'spring_avg_pct_DFW',
						# 'spring_avg_pct_DF',
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
						# 'fall_midterm_gpa_avg',
						# 'fall_midterm_gpa_avg_ind',
						# 'spring_midterm_gpa_avg',
						# 'spring_midterm_gpa_avg_ind',
						# 'cum_adj_transfer_hours',
						'resident',
						# 'father_wsu_flag',
						# 'mother_wsu_flag',
						'parent1_highest_educ_lvl',
						'parent2_highest_educ_lvl',
						# 'citizenship_country',
						'gini_indx',
						'pvrt_rate',
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
						# 'term_withdrawn_hours',
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
							'min_week_from_term_begin_dt',
							# 'max_week_from_term_begin_dt',
							# 'count_week_from_term_begin_dt',
							# 'marital_status',
							'distance',
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
							'high_school_gpa',
							# 'fall_cum_gpa',
							# 'spring_midterm_gpa_change',
							# 'awe_instrument',
							# 'cdi_instrument',
							'fall_avg_difficulty',
							'fall_avg_pct_withdrawn',
							# 'fall_avg_pct_CDFW',
							'fall_avg_pct_CDF',
							# 'fall_avg_pct_DFW',
							# 'fall_avg_pct_DF',
							# 'spring_avg_difficulty',
							# 'spring_avg_pct_withdrawn',
							# 'spring_avg_pct_CDFW',
							# 'spring_avg_pct_CDF',
							# 'spring_avg_pct_DFW',
							# 'spring_avg_pct_DF',
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
							# 'fall_midterm_gpa_avg',
							# 'fall_midterm_gpa_avg_ind',
							# 'spring_midterm_gpa_avg',
							# 'spring_midterm_gpa_avg_ind',
							# 'cum_adj_transfer_hours',
							'resident',
							# 'father_wsu_flag',
							# 'mother_wsu_flag',
							'parent1_highest_educ_lvl',
							'parent2_highest_educ_lvl',
							# 'citizenship_country',
							'gini_indx',
							'pvrt_rate',
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
							# 'term_withdrawn_hours',
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

trici_testing_set = testing_set[(testing_set['campus'] == 'TRICI') & (testing_set['adj_admit_type_cat'] == 'FRSH')][[
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
							'min_week_from_term_begin_dt',
							# 'max_week_from_term_begin_dt',
							# 'count_week_from_term_begin_dt',
							# 'marital_status',
							'distance',
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
							'high_school_gpa',
							# 'fall_cum_gpa',
							# 'spring_midterm_gpa_change',
							# 'awe_instrument',
							# 'cdi_instrument',
							'fall_avg_difficulty',
							'fall_avg_pct_withdrawn',
							# 'fall_avg_pct_CDFW',
							'fall_avg_pct_CDF',
							# 'fall_avg_pct_DFW',
							# 'fall_avg_pct_DF',
							# 'spring_avg_difficulty',
							# 'spring_avg_pct_withdrawn',
							# 'spring_avg_pct_CDFW',
							# 'spring_avg_pct_CDF',
							# 'spring_avg_pct_DFW',
							# 'spring_avg_pct_DF',
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
							# 'fall_midterm_gpa_avg',
							# 'fall_midterm_gpa_avg_ind',
							# 'spring_midterm_gpa_avg',
							# 'spring_midterm_gpa_avg_ind',
							# 'cum_adj_transfer_hours',
							'resident',
							# 'father_wsu_flag',
							# 'mother_wsu_flag',
							'parent1_highest_educ_lvl',
							'parent2_highest_educ_lvl',
							# 'citizenship_country',
							'gini_indx',
							'pvrt_rate',
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
							# 'term_withdrawn_hours',
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
                            'emplid'
                            # 'enrl_ind'
                            ]].copy(deep=True)

#%%
# Detect and remove outliers
print('\nDetect and remove outliers...')

# Pullman outliers
pullm_x_outlier = pullm_training_set.drop(columns='enrl_ind')

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
									# 'mother_wsu_flag',
									# 'father_wsu_flag',
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
vanco_x_outlier = vanco_training_set.drop(columns='enrl_ind')

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
trici_x_outlier = trici_training_set.drop(columns='enrl_ind')

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
						'min_week_from_term_begin_dt',
						# 'max_week_from_term_begin_dt',
						# 'count_week_from_term_begin_dt',
						# 'marital_status',
						'distance',
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
						'high_school_gpa',
						# 'fall_cum_gpa',
						# 'spring_midterm_gpa_change',
						# 'awe_instrument',
						# 'cdi_instrument',
						'fall_avg_difficulty',
						'fall_avg_pct_withdrawn',
						# 'fall_avg_pct_CDFW',
						'fall_avg_pct_CDF',
						# 'fall_avg_pct_DFW',
						# 'fall_avg_pct_DF',
						# 'spring_avg_difficulty',
						# 'spring_avg_pct_withdrawn',
						# 'spring_avg_pct_CDFW',
						# 'spring_avg_pct_CDF',
						# 'spring_avg_pct_DFW',
						# 'spring_avg_pct_DF',
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
						# 'fall_midterm_gpa_avg',
						# 'fall_midterm_gpa_avg_ind',
						# 'spring_midterm_gpa_avg',
						# 'spring_midterm_gpa_avg_ind',
						# 'cum_adj_transfer_hours',
						'resident',
						# 'father_wsu_flag',
						# 'mother_wsu_flag',
						'parent1_highest_educ_lvl',
						'parent2_highest_educ_lvl',
						# 'citizenship_country',
						'gini_indx',
						'pvrt_rate',
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
						# 'total_fall_units',
						# 'term_withdrawn_hours',
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

pullm_y_train = pullm_training_set['enrl_ind']
pullm_y_test = pullm_testing_set['enrl_ind']

pullm_tomek_prep = make_column_transformer(
	(StandardScaler(), [
						'distance',
						# 'age',
						'min_week_from_term_begin_dt',
						# 'max_week_from_term_begin_dt',
						# 'count_week_from_term_begin_dt',
						# 'sat_erws',
						# 'sat_mss',
						# 'sat_comp',
						# 'attendee_total_visits',
						'pop_dens', 
						# 'qvalue', 
						# 'gini_indx',
						'median_inc',
						# 'pvrt_rate',
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
						# 'term_credit_hours',
						'high_school_gpa',
						# 'awe_instrument',
						# 'cdi_instrument',
						'fall_avg_difficulty',
						# 'fall_avg_pct_withdrawn',
						# 'fall_avg_pct_CDFW',
						# 'fall_avg_pct_CDF',
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
						# 'cum_adj_transfer_hours',
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
									# 'mother_wsu_flag',
									# 'father_wsu_flag',
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
						'min_week_from_term_begin_dt',
						# 'max_week_from_term_begin_dt',
						# 'count_week_from_term_begin_dt',
						# 'marital_status',
						'distance',
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
						'high_school_gpa',
						# 'fall_cum_gpa',
						# 'spring_midterm_gpa_change',
						# 'awe_instrument',
						# 'cdi_instrument',
						'fall_avg_difficulty',
						'fall_avg_pct_withdrawn',
						# 'fall_avg_pct_CDFW',
						'fall_avg_pct_CDF',
						# 'fall_avg_pct_DFW',
						# 'fall_avg_pct_DF',
						# 'spring_avg_difficulty',
						# 'spring_avg_pct_withdrawn',
						# 'spring_avg_pct_CDFW',
						# 'spring_avg_pct_CDF',
						# 'spring_avg_pct_DFW',
						# 'spring_avg_pct_DF',
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
						# 'fall_midterm_gpa_avg',
						# 'fall_midterm_gpa_avg_ind',
						# 'spring_midterm_gpa_avg',
						# 'spring_midterm_gpa_avg_ind',
						# 'cum_adj_transfer_hours',
						'resident',
						# 'father_wsu_flag',
						# 'mother_wsu_flag',
						'parent1_highest_educ_lvl',
						'parent2_highest_educ_lvl',
						# 'citizenship_country',
						'gini_indx',
						'pvrt_rate',
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
						# 'term_withdrawn_hours',
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
vanco_y_test = vanco_testing_set['enrl_ind']

vanco_tomek_prep = make_column_transformer(
	(StandardScaler(), [
						'distance',
						# 'age',
						'min_week_from_term_begin_dt',
						# 'max_week_from_term_begin_dt',
						# 'count_week_from_term_begin_dt',
						# 'sat_erws',
						# 'sat_mss',
						# 'sat_comp',
						# 'attendee_total_visits',
						'pop_dens', 
						# 'qvalue', 
						# 'gini_indx',
						'median_inc',
						# 'pvrt_rate',
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
						# 'term_credit_hours',
						'high_school_gpa',
						# 'awe_instrument',
						# 'cdi_instrument',
						'fall_avg_difficulty',
						# 'fall_avg_pct_withdrawn',
						# 'fall_avg_pct_CDFW',
						# 'fall_avg_pct_CDF',
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
						# 'cum_adj_transfer_hours',
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
						'min_week_from_term_begin_dt',
						# 'max_week_from_term_begin_dt',
						# 'count_week_from_term_begin_dt',
						# 'marital_status',
						'distance',
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
						'high_school_gpa',
						# 'fall_cum_gpa',
						# 'spring_midterm_gpa_change',
						# 'awe_instrument',
						# 'cdi_instrument',
						'fall_avg_difficulty',
						'fall_avg_pct_withdrawn',
						# 'fall_avg_pct_CDFW',
						'fall_avg_pct_CDF',
						# 'fall_avg_pct_DFW',
						# 'fall_avg_pct_DF',
						# 'spring_avg_difficulty',
						# 'spring_avg_pct_withdrawn',
						# 'spring_avg_pct_CDFW',
						# 'spring_avg_pct_CDF',
						# 'spring_avg_pct_DFW',
						# 'spring_avg_pct_DF',
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
						# 'fall_midterm_gpa_avg',
						# 'fall_midterm_gpa_avg_ind',
						# 'spring_midterm_gpa_avg',
						# 'spring_midterm_gpa_avg_ind',
						# 'cum_adj_transfer_hours',
						'resident',
						# 'father_wsu_flag',
						# 'mother_wsu_flag',
						'parent1_highest_educ_lvl',
						'parent2_highest_educ_lvl',
						# 'citizenship_country',
						'gini_indx',
						'pvrt_rate',
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
						# 'term_withdrawn_hours',
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
trici_y_test = trici_testing_set['enrl_ind']

trici_tomek_prep = make_column_transformer(
	(StandardScaler(), [
						'distance',
						# 'age',
						'min_week_from_term_begin_dt',
						# 'max_week_from_term_begin_dt',
						# 'count_week_from_term_begin_dt',
						# 'sat_erws',
						# 'sat_mss',
						# 'sat_comp',
						# 'attendee_total_visits',
						'pop_dens', 
						# 'qvalue', 
						# 'gini_indx',
						'median_inc',
						# 'pvrt_rate',
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
						# 'term_credit_hours',
						'high_school_gpa',
						# 'awe_instrument',
						# 'cdi_instrument',
						'fall_avg_difficulty',
						# 'fall_avg_pct_withdrawn',
						# 'fall_avg_pct_CDFW',
						# 'fall_avg_pct_CDF',
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
						# 'cum_adj_transfer_hours',
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

trici_x_train = trici_tomek_prep.fit_transform(trici_x_train)
trici_x_test = trici_tomek_prep.fit_transform(trici_x_test)

trici_under = TomekLinks(sampling_strategy='all', n_jobs=-1)
trici_x_train, trici_y_train = trici_under.fit_resample(trici_x_train, trici_y_train)

trici_tomek_index = trici_under.sample_indices_
trici_training_set = trici_training_set.reset_index(drop=True)

trici_tomek_set = trici_training_set.drop(trici_tomek_index)
trici_tomek_set.to_csv('Z:\\Nathan\\Models\\student_risk\\outliers\\trici_frsh_tomek_set.csv', encoding='utf-8', index=False)

#%%
# Histograms

# Pullman histograms
pullm_x_train.hist(bins=50)
plt.show()

#%%
# Vancouver hisograms
vanco_x_train.hist(bins=50)
plt.show()

#%%
# Tri-Cities hisograms
trici_x_train.hist(bins=50)
plt.show()

#%%
# Correlation matricies

# Pullman correlation matrix
pullm_corr_matrix = pullm_x_train.corr()
smg.plot_corr(pullm_corr_matrix, xnames=pullm_x_train.columns)
plt.show()

#%%
# Pullman correlation matrix
vanco_corr_matrix = vanco_x_train.corr()
smg.plot_corr(vanco_corr_matrix, xnames=vanco_x_train.columns)
plt.show()

#%%
# Tri-Cities correlation matrix
trici_corr_matrix = trici_x_train.corr()
smg.plot_corr(trici_corr_matrix, xnames=trici_x_train.columns)
plt.show()

#%%
# Standard logistic model

# Pullman standard model
pullm_y, pullm_x = dmatrices('enrl_ind ~ distance + pvrt_rate + pop_dens + educ_rate \
				+ city_large + city_mid + city_small + suburb_large + suburb_mid + suburb_small \
				+ male + underrep_minority \
				+ pct_blk + pct_ai + pct_hawi + pct_two + pct_hisp \
                + pell_eligibility_ind \
                + first_gen_flag \
                + fall_avg_difficulty + fall_avg_pct_CDF + fall_avg_pct_withdrawn \
				+ fall_lec_count + fall_lab_count \
				+ total_fall_contact_hrs \
                + resident + gini_indx + median_inc \
            	+ high_school_gpa \
				+ remedial \
				+ parent1_highest_educ_lvl + parent2_highest_educ_lvl \
            	+ unmet_need_ofr \
				+ min_week_from_term_begin_dt', data=pullm_logit_df, return_type='dataframe')

pullm_logit_mod = Logit(pullm_y, pullm_x)
pullm_logit_res = pullm_logit_mod.fit(maxiter=500)
print(pullm_logit_res.summary())

#%%
# Vancouver standard model
vanco_y, vanco_x = dmatrices('enrl_ind ~ distance + pvrt_rate + pop_dens + educ_rate \
				+ male + underrep_minority \
				+ pct_blk + pct_ai + pct_hawi + pct_two + pct_hisp \
                + pell_eligibility_ind \
                + first_gen_flag \
                + fall_avg_difficulty + fall_avg_pct_CDF + fall_avg_pct_withdrawn \
				+ fall_lec_count + fall_lab_count \
				+ total_fall_contact_hrs \
                + resident + gini_indx + median_inc \
            	+ high_school_gpa \
				+ remedial \
				+ parent1_highest_educ_lvl + parent2_highest_educ_lvl \
            	+ unmet_need_ofr \
				+ min_week_from_term_begin_dt', data=vanco_logit_df, return_type='dataframe')

vanco_logit_mod = Logit(vanco_y, vanco_x)
vanco_logit_res = vanco_logit_mod.fit(maxiter=500)
print(vanco_logit_res.summary())

#%%
# Tri-Cities standard model
trici_y, trici_x = dmatrices('enrl_ind ~ distance + pvrt_rate + pop_dens + educ_rate \
				+ male + underrep_minority \
				+ pct_blk + pct_ai + pct_hawi + pct_two + pct_hisp \
                + pell_eligibility_ind \
                + first_gen_flag \
                + fall_avg_difficulty + fall_avg_pct_CDF + fall_avg_pct_withdrawn \
				+ fall_lec_count + fall_lab_count \
				+ total_fall_contact_hrs \
                + resident + gini_indx + median_inc \
            	+ high_school_gpa \
				+ remedial \
				+ parent1_highest_educ_lvl + parent2_highest_educ_lvl \
            	+ unmet_need_ofr \
				+ min_week_from_term_begin_dt', data=trici_logit_df, return_type='dataframe')

trici_logit_mod = Logit(trici_y, trici_x)
trici_logit_res = trici_logit_mod.fit(maxiter=500)
print(trici_logit_res.summary())

#%%
# VIF diagnostic

# Pullman VIF
pullm_vif = pd.DataFrame()
pullm_vif['vif factor'] = [variance_inflation_factor(pullm_x.values, i) for i in range(pullm_x.shape[1])]
pullm_vif['features'] = pullm_x.columns
pullm_vif = pullm_vif.sort_values(by=['vif factor'], ascending=False, inplace=True, ignore_index=True)
print(pullm_vif.round(1).to_string())

#%%
# Vancouver VIF
print('VIF for Vancouver...\n')
vanco_vif = pd.DataFrame()
vanco_vif['vif factor'] = [variance_inflation_factor(vanco_x.values, i) for i in range(vanco_x.shape[1])]
vanco_vif['features'] = vanco_x.columns
vanco_vif = vanco_vif.sort_values(by=['vif factor'], ascending=False, inplace=True, ignore_index=True)
print(vanco_vif.round(1).to_string())

#%%
# Tri-Cities VIF
print('VIF for Tri-Cities...\n')
trici_vif = pd.DataFrame()
trici_vif['vif factor'] = [variance_inflation_factor(trici_x.values, i) for i in range(trici_x.shape[1])]
trici_vif['features'] = trici_x.columns
trici_vif = trici_vif.sort_values(by=['vif factor'], ascending=False, inplace=True, ignore_index=True)
print(trici_vif.round(1).to_string())

#%%
# Logistic model

# Pullman logistic tuning
pullm_hyperparameters = [{'penalty': ['elasticnet'],
                    'l1_ratio': np.linspace(0, 1, 11, endpoint=True),
                    'C': np.logspace(0, 4, 20, endpoint=True)}]

pullm_gridsearch = GridSearchCV(LogisticRegression(solver='saga', class_weight='balanced'), pullm_hyperparameters, cv=5, verbose=0, n_jobs=-1)
pullm_best_model = pullm_gridsearch.fit(pullm_x_train, pullm_y_train)

print(f'Best parameters: {pullm_gridsearch.best_params_}')

#%%
# Pullman logistic
pullm_lreg = LogisticRegression(penalty='elasticnet', solver='saga', class_weight='balanced', max_iter=1000, l1_ratio=0.0, C=1.0, n_jobs=-1, verbose=True).fit(pullm_x_train, pullm_y_train)

pullm_lreg_probs = pullm_lreg.predict_proba(pullm_x_train)
pullm_lreg_probs = pullm_lreg_probs[:, 1]
pullm_lreg_auc = roc_auc_score(pullm_y_train, pullm_lreg_probs)

print(f'Overall accuracy for Pullman logistic model (training): {pullm_lreg.score(pullm_x_train, pullm_y_train):.4f}')
print(f'ROC AUC for Pullman logistic model (training): {pullm_lreg_auc:.4f}')
print(f'Overall accuracy for Pullman logistic model (testing): {pullm_lreg.score(pullm_x_test, pullm_y_test):.4f}')

pullm_lreg_fpr, pullm_lreg_tpr, pullm_thresholds = roc_curve(pullm_y_train, pullm_lreg_probs, drop_intermediate=False)

plt.plot(pullm_lreg_fpr, pullm_lreg_tpr, color='red', lw=2, label='ROC CURVE')
plt.plot([0, 1], [0, 1], color='blue', lw=2, linestyle='--')
plt.xlabel('FALSE-POSITIVE RATE (1 - SPECIFICITY)')
plt.ylabel('TRUE-POSITIVE RATE (SENSITIVITY)')
plt.title('LOGISTIC ROC CURVE (TRAINING)')
plt.show()

#%%
# Pullman confusion matrix
pullm_lreg_matrix = confusion_matrix(pullm_y_test, pullm_lreg.predict(pullm_x_test))
pullm_lreg_df = pd.DataFrame(pullm_lreg_matrix)

sns.heatmap(pullm_lreg_df, annot=True, fmt='d', cbar=None, cmap='Blues')
plt.title('LOGISTIC CONFUSION MATRIX'), plt.tight_layout()
plt.ylabel('TRUE CLASS'), plt.xlabel('PREDICTED CLASS')
plt.show()

#%%
# Vancouver logistic tuning
vanco_hyperparameters = [{'penalty': ['elasticnet'],
                    'l1_ratio': np.linspace(0, 1, 11, endpoint=True),
                    'C': np.logspace(0, 4, 20, endpoint=True)}]

vanco_gridsearch = GridSearchCV(LogisticRegression(solver='saga', class_weight='balanced'), vanco_hyperparameters, cv=5, verbose=0, n_jobs=-1)
vanco_best_model = vanco_gridsearch.fit(vanco_x_train, vanco_y_train)

print(f'Best parameters: {vanco_gridsearch.best_params_}')

#%%
# Vancouver logistic
vanco_lreg = LogisticRegression(penalty='elasticnet', solver='saga', class_weight='balanced', max_iter=1000, l1_ratio=0.0, C=1.0, n_jobs=-1, verbose=True).fit(vanco_x_train, vanco_y_train)

vanco_lreg_probs = vanco_lreg.predict_proba(vanco_x_train)
vanco_lreg_probs = vanco_lreg_probs[:, 1]
vanco_lreg_auc = roc_auc_score(vanco_y_train, vanco_lreg_probs)

print(f'Overall accuracy for Vancouver logistic model (training): {vanco_lreg.score(vanco_x_train, vanco_y_train):.4f}')
print(f'ROC AUC for Vancouver logistic model (training): {vanco_lreg_auc:.4f}')
print(f'Overall accuracy for Vancouver logistic model (testing): {vanco_lreg.score(vanco_x_test, vanco_y_test):.4f}')

vanco_lreg_fpr, vanco_lreg_tpr, vanco_thresholds = roc_curve(vanco_y_train, vanco_lreg_probs, drop_intermediate=False)

plt.plot(vanco_lreg_fpr, vanco_lreg_tpr, color='red', lw=2, label='ROC CURVE')
plt.plot([0, 1], [0, 1], color='blue', lw=2, linestyle='--')
plt.xlabel('FALSE-POSITIVE RATE (1 - SPECIFICITY)')
plt.ylabel('TRUE-POSITIVE RATE (SENSITIVITY)')
plt.title('LOGISTIC ROC CURVE (TRAINING)')
plt.show()

#%%
# Vancouver confusion matrix
vanco_lreg_matrix = confusion_matrix(vanco_y_test, vanco_lreg.predict(vanco_x_test))
vanco_lreg_df = pd.DataFrame(vanco_lreg_matrix)

sns.heatmap(vanco_lreg_df, annot=True, fmt='d', cbar=None, cmap='Blues')
plt.title('LOGISTIC CONFUSION MATRIX'), plt.tight_layout()
plt.ylabel('TRUE CLASS'), plt.xlabel('PREDICTED CLASS')
plt.show()

#%%
# Tri-Cities logistic tuning
trici_hyperparameters = [{'penalty': ['elasticnet'],
                    'l1_ratio': np.linspace(0, 1, 11, endpoint=True),
                    'C': np.logspace(0, 4, 20, endpoint=True)}]

trici_gridsearch = GridSearchCV(LogisticRegression(solver='saga', class_weight='balanced'), trici_hyperparameters, cv=5, verbose=0, n_jobs=-1)
trici_best_model = trici_gridsearch.fit(trici_x_train, trici_y_train)

print(f'Best parameters: {trici_gridsearch.best_params_}')

#%%
# Tri-Cities logistic
trici_lreg = LogisticRegression(penalty='elasticnet', solver='saga', class_weight='balanced', max_iter=1000, l1_ratio=0.0, C=1.0, n_jobs=-1, verbose=True).fit(trici_x_train, trici_y_train)

trici_lreg_probs = trici_lreg.predict_proba(trici_x_train)
trici_lreg_probs = trici_lreg_probs[:, 1]
trici_lreg_auc = roc_auc_score(trici_y_train, trici_lreg_probs)

print(f'Overall accuracy for Tri-Cities logistic model (training): {trici_lreg.score(trici_x_train, trici_y_train):.4f}')
print(f'ROC AUC for Tri-Cities logistic model (training): {trici_lreg_auc:.4f}')
print(f'Overall accuracy for Tri-Cities logistic model (testing): {trici_lreg.score(trici_x_test, trici_y_test):.4f}')

trici_lreg_fpr, trici_lreg_tpr, trici_thresholds = roc_curve(trici_y_train, trici_lreg_probs, drop_intermediate=False)

plt.plot(trici_lreg_fpr, trici_lreg_tpr, color='red', lw=2, label='ROC CURVE')
plt.plot([0, 1], [0, 1], color='blue', lw=2, linestyle='--')
plt.xlabel('FALSE-POSITIVE RATE (1 - SPECIFICITY)')
plt.ylabel('TRUE-POSITIVE RATE (SENSITIVITY)')
plt.title('LOGISTIC ROC CURVE (TRAINING)')
plt.show()

#%%
# Tri-Cities confusion matrix
trici_lreg_matrix = confusion_matrix(trici_y_test, trici_lreg.predict(trici_x_test))
trici_lreg_df = pd.DataFrame(trici_lreg_matrix)

sns.heatmap(trici_lreg_df, annot=True, fmt='d', cbar=None, cmap='Blues')
plt.title('LOGISTIC CONFUSION MATRIX'), plt.tight_layout()
plt.ylabel('TRUE CLASS'), plt.xlabel('PREDICTED CLASS')
plt.show()

#%%
# Stochastic gradient descent model

# Pullman SGD
pullm_sgd = SGDClassifier(loss='modified_huber', penalty='elasticnet', class_weight='balanced', early_stopping=False, max_iter=5000, l1_ratio=0.0, learning_rate='adaptive', eta0=0.0001, tol=0.0001, n_iter_no_change=100, n_jobs=-1, verbose=True).fit(pullm_x_train, pullm_y_train)

pullm_sgd_probs = pullm_sgd.predict_proba(pullm_x_train)
pullm_sgd_probs = pullm_sgd_probs[:, 1]
pullm_sgd_auc = roc_auc_score(pullm_y_train, pullm_sgd_probs)

print(f'\nOverall accuracy for Pullman SGD model (training): {pullm_sgd.score(pullm_x_train, pullm_y_train):.4f}')
print(f'ROC AUC for Pullman SGD model (training): {pullm_sgd_auc:.4f}')
print(f'Overall accuracy for Pullman SGD model (testing): {pullm_sgd.score(pullm_x_test, pullm_y_test):.4f}')

pullm_sgd_fpr, pullm_sgd_tpr, pullm_thresholds = roc_curve(pullm_y_train, pullm_sgd_probs, drop_intermediate=False)

plt.plot(pullm_sgd_fpr, pullm_sgd_tpr, color='red', lw=2, label='ROC CURVE')
plt.plot([0, 1], [0, 1], color='blue', lw=2, linestyle='--')
plt.xlabel('FALSE-POSITIVE RATE (1 - SPECIFICITY)')
plt.ylabel('TRUE-POSITIVE RATE (SENSITIVITY)')
plt.title('SGD ROC CURVE (TRAINING)')
plt.show()

#%%
# Pullman SGD confusion matrix
pullm_sgd_matrix = confusion_matrix(pullm_y_test, pullm_sgd.predict(pullm_x_test))
pullm_sgd_df = pd.DataFrame(pullm_sgd_matrix)

sns.heatmap(pullm_sgd_df, annot=True, fmt='d', cbar=None, cmap='Blues')
plt.title('SGD CONFUSION MATRIX'), plt.tight_layout()
plt.ylabel('TRUE CLASS'), plt.xlabel('PREDICTED CLASS')
plt.show()

#%%
# Vancouver SGD
vanco_sgd = SGDClassifier(loss='modified_huber', penalty='elasticnet', class_weight='balanced', early_stopping=False, max_iter=5000, l1_ratio=0.0, learning_rate='adaptive', eta0=0.0001, tol=0.0001, n_iter_no_change=100, n_jobs=-1, verbose=True).fit(vanco_x_train, vanco_y_train)

vanco_sgd_probs = vanco_sgd.predict_proba(vanco_x_train)
vanco_sgd_probs = vanco_sgd_probs[:, 1]
vanco_sgd_auc = roc_auc_score(vanco_y_train, vanco_sgd_probs)

print(f'\nOverall accuracy for Vancouver SGD model (training): {vanco_sgd.score(vanco_x_train, vanco_y_train):.4f}')
print(f'ROC AUC for Vancouver SGD model (training): {vanco_sgd_auc:.4f}')
print(f'Overall accuracy for Vancouver SGD model (testing): {vanco_sgd.score(vanco_x_test, vanco_y_test):.4f}')

vanco_sgd_fpr, vanco_sgd_tpr, vanco_thresholds = roc_curve(vanco_y_train, vanco_sgd_probs, drop_intermediate=False)

plt.plot(vanco_sgd_fpr, vanco_sgd_tpr, color='red', lw=2, label='ROC CURVE')
plt.plot([0, 1], [0, 1], color='blue', lw=2, linestyle='--')
plt.xlabel('FALSE-POSITIVE RATE (1 - SPECIFICITY)')
plt.ylabel('TRUE-POSITIVE RATE (SENSITIVITY)')
plt.title('SGD ROC CURVE (TRAINING)')
plt.show()

#%%
# Vancouver SGD confusion matrix
vanco_sgd_matrix = confusion_matrix(vanco_y_test, vanco_sgd.predict(vanco_x_test))
vanco_sgd_df = pd.DataFrame(vanco_sgd_matrix)

sns.heatmap(vanco_sgd_df, annot=True, fmt='d', cbar=None, cmap='Blues')
plt.title('SGD CONFUSION MATRIX'), plt.tight_layout()
plt.ylabel('TRUE CLASS'), plt.xlabel('PREDICTED CLASS')
plt.show()

#%%
# Tri-Cities SGD
trici_sgd = SGDClassifier(loss='modified_huber', penalty='elasticnet', class_weight='balanced', early_stopping=False, max_iter=5000, l1_ratio=0.0, learning_rate='adaptive', eta0=0.0001, tol=0.0001, n_iter_no_change=100, n_jobs=-1, verbose=True).fit(trici_x_train, trici_y_train)

trici_sgd_probs = trici_sgd.predict_proba(trici_x_train)
trici_sgd_probs = trici_sgd_probs[:, 1]
trici_sgd_auc = roc_auc_score(trici_y_train, trici_sgd_probs)

print(f'\nOverall accuracy for Tri-Cities SGD model (training): {trici_sgd.score(trici_x_train, trici_y_train):.4f}')
print(f'ROC AUC for Tri-Cities SGD model (training): {trici_sgd_auc:.4f}')
print(f'Overall accuracy for Tri-Cities SGD model (testing): {trici_sgd.score(trici_x_test, trici_y_test):.4f}')

trici_sgd_fpr, trici_sgd_tpr, trici_thresholds = roc_curve(trici_y_train, trici_sgd_probs, drop_intermediate=False)

plt.plot(trici_sgd_fpr, trici_sgd_tpr, color='red', lw=2, label='ROC CURVE')
plt.plot([0, 1], [0, 1], color='blue', lw=2, linestyle='--')
plt.xlabel('FALSE-POSITIVE RATE (1 - SPECIFICITY)')
plt.ylabel('TRUE-POSITIVE RATE (SENSITIVITY)')
plt.title('SGD ROC CURVE (TRAINING)')
plt.show()

#%%
# Tri-Cities SGD confusion matrix
trici_sgd_matrix = confusion_matrix(trici_y_test, trici_sgd.predict(trici_x_test))
trici_sgd_df = pd.DataFrame(trici_sgd_matrix)

sns.heatmap(trici_sgd_df, annot=True, fmt='d', cbar=None, cmap='Blues')
plt.title('SGD CONFUSION MATRIX'), plt.tight_layout()
plt.ylabel('TRUE CLASS'), plt.xlabel('PREDICTED CLASS')
plt.show()

#%%
# Multi-layer perceptron model

# Pullman MLP
pullm_mlp = MLPClassifier(hidden_layer_sizes=(75,50,25), activation='relu', solver='sgd', alpha=2.5, learning_rate_init=0.001, n_iter_no_change=25, max_iter=5000, verbose=True).fit(pullm_x_train, pullm_y_train)

pullm_mlp_probs = pullm_mlp.predict_proba(pullm_x_train)
pullm_mlp_probs = pullm_mlp_probs[:, 1]
pullm_mlp_auc = roc_auc_score(pullm_y_train, pullm_mlp_probs)

print(f'\nOverall accuracy for Pullman multi-layer perceptron model (training): {pullm_mlp.score(pullm_x_train, pullm_y_train):.4f}')
print(f'ROC AUC for Pullman multi-layer perceptron model (training): {pullm_mlp_auc:.4f}')
print(f'Overall accuracy for Pullman multi-layer perceptron model (testing): {pullm_mlp.score(pullm_x_test, pullm_y_test):.4f}')

pullm_mlp_fpr, pullm_mlp_tpr, pullm_thresholds = roc_curve(pullm_y_train, pullm_mlp_probs, drop_intermediate=False)

plt.plot(pullm_mlp_fpr, pullm_mlp_tpr, color='red', lw=2, label='ROC CURVE')
plt.plot([0, 1], [0, 1], color='blue', lw=2, linestyle='--')
plt.xlabel('FALSE-POSITIVE RATE (1 - SPECIFICITY)')
plt.ylabel('TRUE-POSITIVE RATE (SENSITIVITY)')
plt.title('NEURAL NETWORK ROC CURVE (TRAINING)')
plt.show()

#%%
# Pullman MLP confusion matrix
pullm_mlp_matrix = confusion_matrix(pullm_y_test, pullm_mlp.predict(pullm_x_test))
pullm_mlp_df = pd.DataFrame(pullm_mlp_matrix)

sns.heatmap(pullm_mlp_df, annot=True, fmt='d', cbar=None, cmap='Blues')
plt.title('NEURAL NETWORK CONFUSION MATRIX'), plt.tight_layout()
plt.ylabel('TRUE CLASS'), plt.xlabel('PREDICTED CLASS')
plt.show()

#%%
# Vancouver MLP
vanco_mlp = MLPClassifier(hidden_layer_sizes=(75,50,25), activation='relu', solver='sgd', alpha=2.5, learning_rate_init=0.001, n_iter_no_change=25, max_iter=5000, verbose=True).fit(vanco_x_train, vanco_y_train)

vanco_mlp_probs = vanco_mlp.predict_proba(vanco_x_train)
vanco_mlp_probs = vanco_mlp_probs[:, 1]
vanco_mlp_auc = roc_auc_score(vanco_y_train, vanco_mlp_probs)

print(f'\nOverall accuracy for Vancouver multi-layer perceptron model (training): {vanco_mlp.score(vanco_x_train, vanco_y_train):.4f}')
print(f'ROC AUC for Vancouver multi-layer perceptron model (training): {vanco_mlp_auc:.4f}')
print(f'Overall accuracy for Vancouver multi-layer perceptron model (testing): {vanco_mlp.score(vanco_x_test, vanco_y_test):.4f}')

vanco_mlp_fpr, vanco_mlp_tpr, vanco_thresholds = roc_curve(vanco_y_train, vanco_mlp_probs, drop_intermediate=False)

plt.plot(vanco_mlp_fpr, vanco_mlp_tpr, color='red', lw=2, label='ROC CURVE')
plt.plot([0, 1], [0, 1], color='blue', lw=2, linestyle='--')
plt.xlabel('FALSE-POSITIVE RATE (1 - SPECIFICITY)')
plt.ylabel('TRUE-POSITIVE RATE (SENSITIVITY)')
plt.title('NEURAL NETWORK ROC CURVE (TRAINING)')
plt.show()

#%%
# Vancouver MLP confusion matrix
vanco_mlp_matrix = confusion_matrix(vanco_y_test, vanco_mlp.predict(vanco_x_test))
vanco_mlp_df = pd.DataFrame(vanco_mlp_matrix)

sns.heatmap(vanco_mlp_df, annot=True, fmt='d', cbar=None, cmap='Blues')
plt.title('NEURAL NETWORK CONFUSION MATRIX'), plt.tight_layout()
plt.ylabel('TRUE CLASS'), plt.xlabel('PREDICTED CLASS')
plt.show()

#%%
# Tri-Cities MLP
trici_mlp = MLPClassifier(hidden_layer_sizes=(75,50,25), activation='relu', solver='sgd', alpha=2.5, learning_rate_init=0.001, n_iter_no_change=25, max_iter=5000, verbose=True).fit(trici_x_train, trici_y_train)

trici_mlp_probs = trici_mlp.predict_proba(trici_x_train)
trici_mlp_probs = trici_mlp_probs[:, 1]
trici_mlp_auc = roc_auc_score(trici_y_train, trici_mlp_probs)

print(f'\nOverall accuracy for Tri-Cities multi-layer perceptron model (training): {trici_mlp.score(trici_x_train, trici_y_train):.4f}')
print(f'ROC AUC for Tri-Cities multi-layer perceptron model (training): {trici_mlp_auc:.4f}')
print(f'Overall accuracy for Tri-Cities multi-layer perceptron model (testing): {trici_mlp.score(trici_x_test, trici_y_test):.4f}')

trici_mlp_fpr, trici_mlp_tpr, trici_thresholds = roc_curve(trici_y_train, trici_mlp_probs, drop_intermediate=False)

plt.plot(trici_mlp_fpr, trici_mlp_tpr, color='red', lw=2, label='ROC CURVE')
plt.plot([0, 1], [0, 1], color='blue', lw=2, linestyle='--')
plt.xlabel('FALSE-POSITIVE RATE (1 - SPECIFICITY)')
plt.ylabel('TRUE-POSITIVE RATE (SENSITIVITY)')
plt.title('NEURAL NETWORK ROC CURVE (TRAINING)')
plt.show()

#%%
# Tri-Cities MLP confusion matrix
trici_mlp_matrix = confusion_matrix(trici_y_test, trici_mlp.predict(trici_x_test))
trici_mlp_df = pd.DataFrame(trici_mlp_matrix)

sns.heatmap(trici_mlp_df, annot=True, fmt='d', cbar=None, cmap='Blues')
plt.title('NEURAL NETWORK CONFUSION MATRIX'), plt.tight_layout()
plt.ylabel('TRUE CLASS'), plt.xlabel('PREDICTED CLASS')
plt.show()

#%%
# Ensemble model

# Pullman VCF
pullm_vcf = VotingClassifier(estimators=[('lreg', pullm_lreg), ('sgd', pullm_sgd)], voting='soft', weights=[1, 1]).fit(pullm_x_train, pullm_y_train)

pullm_vcf_probs_train = pullm_vcf.predict_proba(pullm_x_train)
pullm_vcf_probs_train = pullm_vcf_probs_train[:, 1]
pullm_vcf_auc_train = roc_auc_score(pullm_y_train, pullm_vcf_probs_train)

pullm_vcf_probs_test = pullm_vcf.predict_proba(pullm_x_test)
pullm_vcf_probs_test = pullm_vcf_probs_test[:, 1]
pullm_vcf_auc_test = roc_auc_score(pullm_y_test, pullm_vcf_probs_test)

print(f'\nOverall accuracy for Pullman ensemble model (training): {pullm_vcf.score(pullm_x_train, pullm_y_train):.4f}')
print(f'ROC AUC for Pullman ensemble model (training): {pullm_vcf_auc_train:.4f}')

pullm_vcf_fpr_train, pullm_vcf_tpr_train, pullm_thresholds_train = roc_curve(pullm_y_train, pullm_vcf_probs_train, drop_intermediate=False)

plt.plot(pullm_vcf_fpr_train, pullm_vcf_tpr_train, color=wsu_color, lw=4, label='ROC CURVE')
plt.plot([0, 1], [0, 1], color='black', lw=4, linestyle='--')
plt.xlabel('FALSE-POSITIVE RATE (1 - SPECIFICITY)')
plt.ylabel('TRUE-POSITIVE RATE (SENSITIVITY)')
plt.title('ENSEMBLE ROC CURVE (TRAINING)')
plt.show()

print(f'Overall accuracy for Pullman ensemble model (testing): {pullm_vcf.score(pullm_x_test, pullm_y_test):.4f}')
print(f'ROC AUC for Pullman ensemble model (testing): {pullm_vcf_auc_test:.4f}')

pullm_vcf_fpr_test, pullm_vcf_tpr_test, pullm_thresholds_test = roc_curve(pullm_y_test, pullm_vcf_probs_test, drop_intermediate=False)

plt.plot(pullm_vcf_fpr_test, pullm_vcf_tpr_test, color=wsu_color, lw=4, label='ROC CURVE')
plt.plot([0, 1], [0, 1], color='black', lw=4, linestyle='--')
plt.xlabel('FALSE-POSITIVE RATE (1 - SPECIFICITY)')
plt.ylabel('TRUE-POSITIVE RATE (SENSITIVITY)')
plt.title('ENSEMBLE ROC CURVE (TESTING)')
plt.show()

#%%
# Pullman VCF confusion matrix
pullm_vcf_matrix = confusion_matrix(pullm_y_test, pullm_vcf.predict(pullm_x_test))
pullm_vcf_df = pd.DataFrame(pullm_vcf_matrix)

sns.heatmap(pullm_vcf_df, annot=True, fmt='d', cbar=None, cmap='Blues')
plt.title('ENSEMBLE CONFUSION MATRIX'), plt.tight_layout()
plt.ylabel('TRUE CLASS'), plt.xlabel('PREDICTED CLASS')
plt.show()

#%%
# Vancouver VCF
vanco_vcf = VotingClassifier(estimators=[('lreg', vanco_lreg), ('sgd', vanco_sgd)], voting='soft', weights=[1, 1]).fit(vanco_x_train, vanco_y_train)

vanco_vcf_probs = vanco_vcf.predict_proba(vanco_x_train)
vanco_vcf_probs = vanco_vcf_probs[:, 1]
vanco_vcf_auc = roc_auc_score(vanco_y_train, vanco_vcf_probs)

print(f'\nOverall accuracy for Vancouver ensemble model (training): {vanco_vcf.score(vanco_x_train, vanco_y_train):.4f}')
print(f'ROC AUC for Vancouver ensemble model (training): {vanco_vcf_auc:.4f}')
print(f'Overall accuracy for Vancouver ensemble model (testing): {vanco_vcf.score(vanco_x_test, vanco_y_test):.4f}')

vanco_vcf_fpr, vanco_vcf_tpr, vanco_thresholds = roc_curve(vanco_y_train, vanco_vcf_probs, drop_intermediate=False)

plt.plot(vanco_vcf_fpr, vanco_vcf_tpr, color='red', lw=2, label='ROC CURVE')
plt.plot([0, 1], [0, 1], color='blue', lw=2, linestyle='--')
plt.xlabel('FALSE-POSITIVE RATE (1 - SPECIFICITY)')
plt.ylabel('TRUE-POSITIVE RATE (SENSITIVITY)')
plt.title('ENSEMBLE ROC CURVE (TRAINING)')
plt.show()

#%%
# Vancouver VCF confusion matrix
vanco_vcf_matrix = confusion_matrix(vanco_y_test, vanco_vcf.predict(vanco_x_test))
vanco_vcf_df = pd.DataFrame(vanco_vcf_matrix)

sns.heatmap(vanco_vcf_df, annot=True, fmt='d', cbar=None, cmap='Blues')
plt.title('ENSEMBLE CONFUSION MATRIX'), plt.tight_layout()
plt.ylabel('TRUE CLASS'), plt.xlabel('PREDICTED CLASS')
plt.show()

#%%
# Tri-Cities VCF
trici_vcf = VotingClassifier(estimators=[('lreg', trici_lreg), ('sgd', trici_sgd)], voting='soft', weights=[1, 1]).fit(trici_x_train, trici_y_train)

trici_vcf_probs = trici_vcf.predict_proba(trici_x_train)
trici_vcf_probs = trici_vcf_probs[:, 1]
trici_vcf_auc = roc_auc_score(trici_y_train, trici_vcf_probs)

print(f'\nOverall accuracy for Tri-Cities ensemble model (training): {trici_vcf.score(trici_x_train, trici_y_train):.4f}')
print(f'ROC AUC for Tri-Cities ensemble model (training): {trici_vcf_auc:.4f}')
print(f'Overall accuracy for Tri-Cities ensemble model (testing): {trici_vcf.score(trici_x_test, trici_y_test):.4f}')

trici_vcf_fpr, trici_vcf_tpr, trici_thresholds = roc_curve(trici_y_train, trici_vcf_probs, drop_intermediate=False)

plt.plot(trici_vcf_fpr, trici_vcf_tpr, color='red', lw=2, label='ROC CURVE')
plt.plot([0, 1], [0, 1], color='blue', lw=2, linestyle='--')
plt.xlabel('FALSE-POSITIVE RATE (1 - SPECIFICITY)')
plt.ylabel('TRUE-POSITIVE RATE (SENSITIVITY)')
plt.title('ENSEMBLE ROC CURVE (TRAINING)')
plt.show()

#%%
# Tri-Cities VCF confusion matrix
trici_vcf_matrix = confusion_matrix(trici_y_test, trici_vcf.predict(trici_x_test))
trici_vcf_df = pd.DataFrame(trici_vcf_matrix)

sns.heatmap(trici_vcf_df, annot=True, fmt='d', cbar=None, cmap='Blues')
plt.title('ENSEMBLE CONFUSION MATRIX'), plt.tight_layout()
plt.ylabel('TRUE CLASS'), plt.xlabel('PREDICTED CLASS')
plt.show()

#%%
# Prepare model predictions

# Pullman probabilites
pullm_lreg_pred_probs = pullm_lreg.predict_proba(pullm_x_test)
pullm_lreg_pred_probs = pullm_lreg_pred_probs[:, 1]
pullm_sgd_pred_probs = pullm_sgd.predict_proba(pullm_x_test)
pullm_sgd_pred_probs = pullm_sgd_pred_probs[:, 1]
pullm_mlp_pred_probs = pullm_mlp.predict_proba(pullm_x_test)
pullm_mlp_pred_probs = pullm_mlp_pred_probs[:, 1]
pullm_vcf_pred_probs = pullm_vcf.predict_proba(pullm_x_test)
pullm_vcf_pred_probs = pullm_vcf_pred_probs[:, 1]

#%%
# Vancouver probabilites
vanco_lreg_pred_probs = vanco_lreg.predict_proba(vanco_x_test)
vanco_lreg_pred_probs = vanco_lreg_pred_probs[:, 1]
vanco_sgd_pred_probs = vanco_sgd.predict_proba(vanco_x_test)
vanco_sgd_pred_probs = vanco_sgd_pred_probs[:, 1]
vanco_mlp_pred_probs = vanco_mlp.predict_proba(vanco_x_test)
vanco_mlp_pred_probs = vanco_mlp_pred_probs[:, 1]
vanco_vcf_pred_probs = vanco_vcf.predict_proba(vanco_x_test)
vanco_vcf_pred_probs = vanco_vcf_pred_probs[:, 1]

#%%
# Tri-Cities probabilities
trici_lreg_pred_probs = trici_lreg.predict_proba(trici_x_test)
trici_lreg_pred_probs = trici_lreg_pred_probs[:, 1]
trici_sgd_pred_probs = trici_sgd.predict_proba(trici_x_test)
trici_sgd_pred_probs = trici_sgd_pred_probs[:, 1]
trici_mlp_pred_probs = trici_mlp.predict_proba(trici_x_test)
trici_mlp_pred_probs = trici_mlp_pred_probs[:, 1]
trici_vcf_pred_probs = trici_vcf.predict_proba(trici_x_test)
trici_vcf_pred_probs = trici_vcf_pred_probs[:, 1]

#%%
# Output model predictions to file

# Pullman predicted outcome
pullm_pred_outcome['lr_prob'] = pd.DataFrame(pullm_lreg_pred_probs)
pullm_pred_outcome['lr_pred'] = pullm_lreg.predict(pullm_x_test)
pullm_pred_outcome['sgd_prob'] = pd.DataFrame(pullm_sgd_pred_probs)
pullm_pred_outcome['sgd_pred'] = pullm_sgd.predict(pullm_x_test)
pullm_pred_outcome['mlp_prob'] = pd.DataFrame(pullm_mlp_pred_probs)
pullm_pred_outcome['mlp_pred'] = pullm_mlp.predict(pullm_x_test)
pullm_pred_outcome['vcf_prob'] = pd.DataFrame(pullm_vcf_pred_probs)
pullm_pred_outcome['vcf_pred'] = pullm_vcf.predict(pullm_x_test)

#%%
# Vancouver predicted outcome
vanco_pred_outcome['lr_prob'] = pd.DataFrame(vanco_lreg_pred_probs)
vanco_pred_outcome['lr_pred'] = vanco_lreg.predict(vanco_x_test)
vanco_pred_outcome['sgd_prob'] = pd.DataFrame(vanco_sgd_pred_probs)
vanco_pred_outcome['sgd_pred'] = vanco_sgd.predict(vanco_x_test)
vanco_pred_outcome['mlp_prob'] = pd.DataFrame(vanco_mlp_pred_probs)
vanco_pred_outcome['mlp_pred'] = vanco_mlp.predict(vanco_x_test)
vanco_pred_outcome['vcf_prob'] = pd.DataFrame(vanco_vcf_pred_probs)
vanco_pred_outcome['vcf_pred'] = vanco_vcf.predict(vanco_x_test)

#%%
# Tri-Cities predicted outcome
trici_pred_outcome['lr_prob'] = pd.DataFrame(trici_lreg_pred_probs)
trici_pred_outcome['lr_pred'] = trici_lreg.predict(trici_x_test)
trici_pred_outcome['sgd_prob'] = pd.DataFrame(trici_sgd_pred_probs)
trici_pred_outcome['sgd_pred'] = trici_sgd.predict(trici_x_test)
trici_pred_outcome['mlp_prob'] = pd.DataFrame(trici_mlp_pred_probs)
trici_pred_outcome['mlp_pred'] = trici_mlp.predict(trici_x_test)
trici_pred_outcome['vcf_prob'] = pd.DataFrame(trici_vcf_pred_probs)
trici_pred_outcome['vcf_pred'] = trici_vcf.predict(trici_x_test)
