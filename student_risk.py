#%%
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import statsmodels.graphics.api as smg
from matplotlib.legend_handler import HandlerLine2D
from patsy import dmatrices
from statsmodels.api import OLS
from statsmodels.discrete.discrete_model import Logit
from statsmodels.stats.outliers_influence import variance_inflation_factor
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import make_column_transformer
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder, PolynomialFeatures, StandardScaler
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.svm import SVC, LinearSVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix, roc_curve, roc_auc_score
from sklearn.model_selection import cross_val_score
from sklearn.model_selection import GridSearchCV
from sklearn.model_selection import RepeatedStratifiedKFold

#%%
# Import pre-split data
training_set = pd.read_csv('Z:\\Nathan\\Models\\student_risk\\training_set.csv', encoding='utf-8')
testing_set = pd.read_csv('Z:\\Nathan\\Models\\student_risk\\testing_set.csv', encoding='utf-8')

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
                            'avg_difficulty'                
                            ]].dropna()

cdi_x_train = training_cdi[[
                            'high_school_gpa',
                            'class_count',
                            'sat_erws',
                            'sat_mss',
                            'underrep_minority',
                            'male',
                            'median_inc'  
                            ]]

cdi_y_train = training_cdi[[
                            'avg_difficulty'
                            ]]

y, x = dmatrices('avg_difficulty ~ high_school_gpa + class_count + sat_erws + sat_mss + underrep_minority + male + median_inc', data=training_cdi, return_type='dataframe')
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
                            'avg_difficulty'                
                            ]].dropna()

cdi_x_test = testing_cdi[[
                            'high_school_gpa',
                            'class_count',
                            'sat_erws',
                            'sat_mss',
                            'underrep_minority',
                            'male',
                            'median_inc'  
                            ]]

cdi_y_test = testing_cdi[[
                            'avg_difficulty'
                            ]]

y, x = dmatrices('avg_difficulty ~ high_school_gpa + class_count + sat_erws + sat_mss + underrep_minority + male + median_inc', data=testing_cdi, return_type='dataframe')
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
logit_df = training_set[[
                        'enrl_ind', 
                        # 'acad_year',
                        # 'age_group', 
                        'age',
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
                        'LSAMP_STEM_Flag',
                        # 'anywhere_STEM_Flag',
                        'high_school_gpa',
                        'awe_instrument',
                        'cdi_instrument',
                        'avg_difficulty',
                        'cum_adj_transfer_hours',
                        'resident',
                        'father_wsu_flag',
                        'mother_wsu_flag',
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
                        'pct_asn',
                        'pct_hawi',
                        'pct_oth',
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
                        'AD_DTA',
                        'AD_AST',
                        'AP',
                        'RS',
                        'CHS',
                        'IB',
                        'AICE', 
                        'term_credit_hours',
                        'athlete',
                        'remedial',
                        # 'ACAD_PLAN',
                        # 'plan_owner_org',
                        # 'business',
                        'cahnrext',
                        'cas',
                        'comm',
                        'education',
                        'med_sci',
                        'medicine',
                        'nursing',
                        'pharmacy',
                        'provost',
                        'vcea',
                        'vet_med',
                        # 'last_sch_proprietorship',
                        # 'sat_erws',
                        # 'sat_mss',
                        # 'sat_comp',
                        'attendee_alive',
                        'attendee_campus_visit',
                        'attendee_cashe',
                        'attendee_destination',
                        'attendee_experience',
                        'attendee_fcd_pullman',
                        'attendee_fced',
                        'attendee_fcoc',
                        'attendee_fcod',
                        'attendee_group_visit',
                        'attendee_honors_visit',
                        'attendee_imagine_tomorrow',
                        'attendee_imagine_u',
                        'attendee_la_bienvenida',
                        'attendee_lvp_camp',
                        'attendee_oos_destination',
                        'attendee_oos_experience',
                        'attendee_preview',
                        'attendee_preview_jrs',
                        'attendee_shaping',
                        'attendee_top_scholars',
                        'attendee_transfer_day',
                        'attendee_vibes',
                        'attendee_welcome_center',
                        # 'attendee_any_visitation_ind',
                        'attendee_total_visits',
                        # 'qvalue',
                        'fed_efc',
                        'fed_need',
                        'unmet_need_ofr'
                        ]].dropna()

training_set = training_set[[
                            'emplid',
                            'enrl_ind', 
                            # 'acad_year',
                            # 'age_group', 
                            'age', 
                            'male',
                            # 'min_week_from_term_begin_dt',
                            # 'max_week_from_term_begin_dt',
                            'count_week_from_term_begin_dt',
                            # 'marital_status',
                            # 'Distance',
                            # 'pop_dens',
                            # 'underrep_minority', 
                            'ipeds_ethnic_group_descrshort',
                            'pell_eligibility_ind', 
                            # 'pell_recipient_ind',
                            'first_gen_flag',
                            'LSAMP_STEM_Flag',
                            # 'anywhere_STEM_Flag', 
                            'high_school_gpa', 
                            'awe_instrument',
                            'cdi_instrument',
                            'avg_difficulty',
                            'cum_adj_transfer_hours',
                            'resident',
                            'father_wsu_flag',
                            'mother_wsu_flag',
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
                            'pct_asn',
                            'pct_hawi',
                            'pct_oth',
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
                            'AD_DTA',
                            'AD_AST',
                            'AP',
                            'RS',
                            'CHS',
                            'IB',
                            'AICE', 
                            'term_credit_hours',
                            'athlete',
                            'remedial',
                            # 'ACAD_PLAN',
                            # 'plan_owner_org',
                            # 'business',
                            'cahnrext',
                            'cas',
                            'comm',
                            'education',
                            'med_sci',
                            'medicine',
                            'nursing',
                            'pharmacy',
                            'provost',
                            'vcea',
                            'vet_med',
                            # 'last_sch_proprietorship',
                            # 'sat_erws',
                            # 'sat_mss',
                            # 'sat_comp',
                            'attendee_alive',
                            'attendee_campus_visit',
                            'attendee_cashe',
                            'attendee_destination',
                            'attendee_experience',
                            'attendee_fcd_pullman',
                            'attendee_fced',
                            'attendee_fcoc',
                            'attendee_fcod',
                            'attendee_group_visit',
                            'attendee_honors_visit',
                            'attendee_imagine_tomorrow',
                            'attendee_imagine_u',
                            'attendee_la_bienvenida',
                            'attendee_lvp_camp',
                            'attendee_oos_destination',
                            'attendee_oos_experience',
                            'attendee_preview',
                            'attendee_preview_jrs',
                            'attendee_shaping',
                            'attendee_top_scholars',
                            'attendee_transfer_day',
                            'attendee_vibes',
                            'attendee_welcome_center',
                            'attendee_any_visitation_ind',
                            # 'attendee_total_visits',
                            # 'qvalue',
                            'fed_efc',
                            'fed_need',
                            'unmet_need_ofr'
                            ]].dropna()

testing_set = testing_set[[
                            'emplid',
                            'enrl_ind', 
                            # 'acad_year',
                            # 'age_group', 
                            'age', 
                            'male',
                            # 'min_week_from_term_begin_dt',
                            # 'max_week_from_term_begin_dt',
                            'count_week_from_term_begin_dt',
                            # 'marital_status',
                            # 'Distance',
                            # 'pop_dens',
                            # 'underrep_minority', 
                            'ipeds_ethnic_group_descrshort',
                            'pell_eligibility_ind', 
                            # 'pell_recipient_ind',
                            'first_gen_flag',
                            'LSAMP_STEM_Flag', 
                            # 'anywhere_STEM_Flag',
                            'high_school_gpa',
                            'awe_instrument',
                            'cdi_instrument',
                            'avg_difficulty',
                            'cum_adj_transfer_hours',
                            'resident',
                            'father_wsu_flag',
                            'mother_wsu_flag',
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
                            'pct_asn',
                            'pct_hawi',
                            'pct_oth',
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
                            'AD_DTA',
                            'AD_AST',
                            'AP',
                            'RS',
                            'CHS',
                            'IB',
                            'AICE', 
                            'term_credit_hours',
                            'athlete',
                            'remedial',
                            # 'ACAD_PLAN',
                            # 'plan_owner_org',
                            # 'business',
                            'cahnrext',
                            'cas',
                            'comm',
                            'education',
                            'med_sci',
                            'medicine',
                            'nursing',
                            'pharmacy',
                            'provost',
                            'vcea',
                            'vet_med',
                            # 'last_sch_proprietorship',
                            # 'sat_erws',
                            # 'sat_mss',
                            # 'sat_comp',
                            'attendee_alive',
                            'attendee_campus_visit',
                            'attendee_cashe',
                            'attendee_destination',
                            'attendee_experience',
                            'attendee_fcd_pullman',
                            'attendee_fced',
                            'attendee_fcoc',
                            'attendee_fcod',
                            'attendee_group_visit',
                            'attendee_honors_visit',
                            'attendee_imagine_tomorrow',
                            'attendee_imagine_u',
                            'attendee_la_bienvenida',
                            'attendee_lvp_camp',
                            'attendee_oos_destination',
                            'attendee_oos_experience',
                            'attendee_preview',
                            'attendee_preview_jrs',
                            'attendee_shaping',
                            'attendee_top_scholars',
                            'attendee_transfer_day',
                            'attendee_vibes',
                            'attendee_welcome_center',
                            'attendee_any_visitation_ind',
                            # 'attendee_total_visits',
                            # 'qvalue',
                            'fed_efc',
                            'fed_need',
                            'unmet_need_ofr'
                            ]].dropna()

testing_set = testing_set.reset_index()

pred_outcome = testing_set[[ 
                            'emplid',
                            'enrl_ind'
                            ]].copy(deep=True)

x_train = training_set[[
                        # 'acad_year',
                        # 'age_group', 
                        'age', 
                        'male',
                        # 'min_week_from_term_begin_dt',
                        # 'max_week_from_term_begin_dt',
                        'count_week_from_term_begin_dt',
                        # 'marital_status',
                        # 'Distance',
                        # 'pop_dens',
                        # 'underrep_minority', 
                        'ipeds_ethnic_group_descrshort',
                        'pell_eligibility_ind', 
                        # 'pell_recipient_ind',
                        'first_gen_flag', 
                        'LSAMP_STEM_Flag',
                        # 'anywhere_STEM_Flag',
                        'high_school_gpa',
                        'awe_instrument', 
                        'cdi_instrument',
                        'avg_difficulty',
                        'cum_adj_transfer_hours',
                        'resident',
                        'father_wsu_flag',
                        'mother_wsu_flag',
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
                        'pct_asn',
                        'pct_hawi',
                        'pct_oth',
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
                        'AD_DTA',
                        'AD_AST',
                        'AP',
                        'RS',
                        'CHS',
                        'IB',
                        'AICE', 
                        'term_credit_hours',
                        'athlete',
                        'remedial',
                        # 'ACAD_PLAN',
                        # 'plan_owner_org',
                        # 'business',
                        'cahnrext',
                        'cas',
                        'comm',
                        'education',
                        'med_sci',
                        'medicine',
                        'nursing',
                        'pharmacy',
                        'provost',
                        'vcea',
                        'vet_med',
                        # 'last_sch_proprietorship',
                        # 'sat_erws',
                        # 'sat_mss',
                        # 'sat_comp',
                        'attendee_alive',
                        'attendee_campus_visit',
                        'attendee_cashe',
                        'attendee_destination',
                        'attendee_experience',
                        'attendee_fcd_pullman',
                        'attendee_fced',
                        'attendee_fcoc',
                        'attendee_fcod',
                        'attendee_group_visit',
                        'attendee_honors_visit',
                        'attendee_imagine_tomorrow',
                        'attendee_imagine_u',
                        'attendee_la_bienvenida',
                        'attendee_lvp_camp',
                        'attendee_oos_destination',
                        'attendee_oos_experience',
                        'attendee_preview',
                        'attendee_preview_jrs',
                        'attendee_shaping',
                        'attendee_top_scholars',
                        'attendee_transfer_day',
                        'attendee_vibes',
                        'attendee_welcome_center',
                        'attendee_any_visitation_ind',
                        # 'attendee_total_visits',
                        # 'qvalue',
                        'fed_efc',
                        'fed_need',
                        'unmet_need_ofr'
                        ]]

x_test = testing_set[[
                        # 'acad_year', 
                        # 'age_group',
                        'age', 
                        'male',
                        # 'min_week_from_term_begin_dt',
                        # 'max_week_from_term_begin_dt',
                        'count_week_from_term_begin_dt',
                        # 'marital_status',
                        # 'Distance',
                        # 'pop_dens',
                        # 'underrep_minority', 
                        'ipeds_ethnic_group_descrshort',
                        'pell_eligibility_ind', 
                        # 'pell_recipient_ind',
                        'first_gen_flag', 
                        'LSAMP_STEM_Flag',
                        # 'anywhere_STEM_Flag',
                        'high_school_gpa',
                        'awe_instrument', 
                        'cdi_instrument',
                        'avg_difficulty',
                        'cum_adj_transfer_hours',
                        'resident',
                        'father_wsu_flag',
                        'mother_wsu_flag',
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
                        'pct_asn',
                        'pct_hawi',
                        'pct_oth',
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
                        'AD_DTA',
                        'AD_AST',
                        'AP',
                        'RS',
                        'CHS',
                        'IB',
                        'AICE', 
                        'term_credit_hours',
                        'athlete',
                        'remedial',
                        # 'ACAD_PLAN',
                        # 'plan_owner_org',
                        # 'business',
                        'cahnrext',
                        'cas',
                        'comm',
                        'education',
                        'med_sci',
                        'medicine',
                        'nursing',
                        'pharmacy',
                        'provost',
                        'vcea',
                        'vet_med',
                        # 'last_sch_proprietorship',
                        # 'sat_erws',
                        # 'sat_mss',
                        # 'sat_comp',
                        'attendee_alive',
                        'attendee_campus_visit',
                        'attendee_cashe',
                        'attendee_destination',
                        'attendee_experience',
                        'attendee_fcd_pullman',
                        'attendee_fced',
                        'attendee_fcoc',
                        'attendee_fcod',
                        'attendee_group_visit',
                        'attendee_honors_visit',
                        'attendee_imagine_tomorrow',
                        'attendee_imagine_u',
                        'attendee_la_bienvenida',
                        'attendee_lvp_camp',
                        'attendee_oos_destination',
                        'attendee_oos_experience',
                        'attendee_preview',
                        'attendee_preview_jrs',
                        'attendee_shaping',
                        'attendee_top_scholars',
                        'attendee_transfer_day',
                        'attendee_vibes',
                        'attendee_welcome_center',
                        'attendee_any_visitation_ind',
                        # 'attendee_total_visits',
                        # 'qvalue',
                        'fed_efc',
                        'fed_need',
                        'unmet_need_ofr'
                        ]]

y_train = training_set['enrl_ind']
y_test = testing_set['enrl_ind']

#%%
# Histograms
x_train.hist(bins=50)
plt.show()

#%%
corr_matrix = x_train.corr()
smg.plot_corr(corr_matrix, xnames=x_train.columns)
plt.show()

#%%
# Preprocess data
preprocess = make_column_transformer(
    (MinMaxScaler(), [
                        'age',
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
                        'term_credit_hours',
                        'high_school_gpa',
                        # 'awe_instrument',
                        # 'cdi_instrument',
                        'avg_difficulty',
                        'cum_adj_transfer_hours',
                        'fed_efc',
                        'fed_need', 
                        'unmet_need_ofr'
                        ]),
    (OneHotEncoder(drop='first'), [
                                    # 'acad_year', 
                                    # 'age_group',
                                    # 'marital_status',
                                    'first_gen_flag',
                                    'LSAMP_STEM_Flag',
                                    # 'anywhere_STEM_Flag', 
                                    # 'ACAD_PLAN',
                                    # 'plan_owner_org',
                                    'ipeds_ethnic_group_descrshort',
                                    # 'last_sch_proprietorship', 
                                    'parent1_highest_educ_lvl',
                                    'parent2_highest_educ_lvl'
                                    ]),
    # (PolynomialFeatures(interaction_only=True), ['male', 'underrep_minority']),
    remainder='passthrough'
)

x_train = preprocess.fit_transform(x_train)
x_test = preprocess.fit_transform(x_test)

#%%
# Standard logistic model
y, x = dmatrices('enrl_ind ~ age + male + count_week_from_term_begin_dt + underrep_minority + pct_blk + pct_ai + pct_asn + pct_hawi + pct_oth + pct_two + pct_hisp \
                + city_large + city_mid + city_small + suburb_large + suburb_mid + suburb_small \
                + pell_eligibility_ind + LSAMP_STEM_Flag + cum_adj_transfer_hours + avg_difficulty + high_school_gpa + awe_instrument + cdi_instrument \
                + resident + father_wsu_flag + mother_wsu_flag + gini_indx + median_inc + educ_rate \
                + parent1_highest_educ_lvl + parent2_highest_educ_lvl + AD_DTA + AD_AST + AP + RS + CHS + IB + AICE + term_credit_hours + athlete + remedial \
                + cahnrext + cas + comm + education + med_sci + medicine + nursing + pharmacy + provost + vcea + vet_med \
                + attendee_total_visits + fed_efc + fed_need + unmet_need_ofr', data=logit_df, return_type='dataframe')

logit_mod = Logit(y, x)
logit_res = logit_mod.fit(maxiter=500)
print(logit_res.summary())

#%%
# VIF diagnostic
vif = pd.DataFrame()
vif['vif factor'] = [variance_inflation_factor(x.values, i) for i in range(x.shape[1])]
vif['features'] = x.columns

print(vif.round(1))

#%%
# Logistic hyperparameter tuning
hyperparameters = [{'penalty': ['l1'],
                    'C': np.logspace(0, 4, 20, endpoint=True)},
                    {'penalty': ['l2'],
                    'C': np.logspace(0, 4, 20, endpoint=True)}]

gridsearch = GridSearchCV(LogisticRegression(solver='saga', class_weight='balanced'), hyperparameters, cv=5, verbose=0, n_jobs=-1)
best_model = gridsearch.fit(x_train, y_train)

print(f'Best parameters: {gridsearch.best_params_}')

#%%
# Logistic model
lreg = LogisticRegression(penalty='l1', solver='saga', class_weight='balanced', max_iter=500, C=2.6367, n_jobs=-1)
lreg.fit(x_train, y_train)

lreg_probs = lreg.predict_proba(x_train)
lreg_probs = lreg_probs[:, 1]
lreg_auc = roc_auc_score(y_train, lreg_probs)

print(f'Overall accuracy for logistic model (training): {lreg.score(x_train, y_train):.4f}')
print(f'ROC AUC for logistic model (training): {lreg_auc:.4f}')
print(f'Overall accuracy for logistic model (testing): {lreg.score(x_test, y_test):.4f}')

lreg_fpr, lreg_tpr, thresholds = roc_curve(y_train, lreg_probs, drop_intermediate=False)

plt.plot(lreg_fpr, lreg_tpr, color='red', lw=2, label='ROC CURVE')
plt.plot([0, 1], [0, 1], color='blue', lw=2, linestyle='--')
plt.xlabel('FALSE-POSITIVE RATE (1 - SPECIFICITY)')
plt.ylabel('TRUE-POSITIVE RATE (SENSITIVITY)')
plt.title('LOGISTIC ROC CURVE (TRAINING)')
plt.show()

#%%
# SVC hyperparameter tuning
hyperparameters = [{'kernel': ['linear'],
                    'C': np.logspace(0, 4, 5, endpoint=True)},
                    {'kernel': ['sigmoid'],
                    'C': np.logspace(0, 4, 5, endpoint=True),
                    'gamma': np.logspace(0, 4, 5, endpoint=True)}]

gridsearch = GridSearchCV(SVC(class_weight='balanced'), hyperparameters, cv=5, verbose=0, n_jobs=-1)
best_model = gridsearch.fit(x_train, y_train)

print(f'Best parameters: {gridsearch.best_params_}')

#%%
# SVC model
svc = SVC(kernel='linear', class_weight='balanced', probability=True)
svc.fit(x_train, y_train)

probs = CalibratedClassifierCV(svc, method='sigmoid', cv='prefit')
probs.fit(x_test, y_test)

svc_probs = svc.predict_proba(x_train)
svc_probs = svc_probs[:, 1]
svc_auc = roc_auc_score(y_train, svc_probs)

print(f'Overall accuracy for linear SVC model (training): {svc.score(x_train, y_train):.4f}')
print(f'ROC AUC for linear SVC model (training): {svc_auc:.4f}')
print(f'Overall accuracy for linear SVC model (testing): {svc.score(x_test, y_test):.4f}')

svc_fpr, svc_tpr, thresholds = roc_curve(y_train, svc_probs, drop_intermediate=False)

plt.plot(svc_fpr, svc_tpr, color='red', lw=2, label='ROC CURVE')
plt.plot([0, 1], [0, 1], color='blue', lw=2, linestyle='--')
plt.xlabel('FALSE-POSITIVE RATE (1 - SPECIFICITY)')
plt.ylabel('TRUE-POSITIVE RATE (SENSITIVITY)')
plt.title('LINEAR SVC ROC CURVE (TRAINING)')
plt.show()

#%%
# Random forest max_depth tuning
max_depths = np.linspace(1, 32, 32, endpoint=True)

train_results = []
test_results = []

for max_depth in max_depths:
    rfc = RandomForestClassifier(class_weight='balanced', n_estimators=500, max_features='sqrt', max_depth=max_depth, n_jobs=-1)
    rfc.fit(x_train, y_train)
    
    rfc_train = rfc.predict_proba(x_train)
    rfc_train = rfc_train[:,1]
    rfc_auc = roc_auc_score(y_train, rfc_train)
    
    rfc_fpr, rfc_tpr, thresholds = roc_curve(y_train, rfc_train, drop_intermediate=False)
    train_results.append(rfc_auc)

    rfc_test = rfc.predict_proba(x_test)
    rfc_test = rfc_test[:,1]
    rfc_auc = roc_auc_score(y_test, rfc_test)

    rfc_fpr, rfc_tpr, thresholds = roc_curve(y_test, rfc_test, drop_intermediate=False)
    test_results.append(rfc_auc)

line1, = plt.plot(max_depths, train_results, 'b', label='AUC (TRAINING)')
line2, = plt.plot(max_depths, test_results, 'r', label='AUC (TESTING)')
plt.legend(handler_map={line1: HandlerLine2D(numpoints=2)})
plt.ylabel('AUC SCORE')
plt.xlabel('TREE DEPTH')
plt.show()

#%%
# Random forest max_features tuning
max_features = np.linspace(0.025, 1, 40, endpoint=True)

train_results = []
test_results = []

for max_feature in max_features:
    rfc = RandomForestClassifier(class_weight='balanced', n_estimators=500, max_depth=7, max_features=max_feature, n_jobs=-1)
    rfc.fit(x_train, y_train)
    
    rfc_train = rfc.predict_proba(x_train)
    rfc_train = rfc_train[:,1]
    rfc_auc = roc_auc_score(y_train, rfc_train)
    
    rfc_fpr, rfc_tpr, thresholds = roc_curve(y_train, rfc_train, drop_intermediate=False)
    train_results.append(rfc_auc)

    rfc_test = rfc.predict_proba(x_test)
    rfc_test = rfc_test[:,1]
    rfc_auc = roc_auc_score(y_test, rfc_test)

    rfc_fpr, rfc_tpr, thresholds = roc_curve(y_test, rfc_test, drop_intermediate=False)
    test_results.append(rfc_auc)

line1, = plt.plot(max_features, train_results, 'b', label='AUC (TRAINING)')
line2, = plt.plot(max_features, test_results, 'r', label='AUC (TESTING)')
plt.legend(handler_map={line1: HandlerLine2D(numpoints=2)})
plt.ylabel('AUC SCORE')
plt.xlabel('MAX FEATURES')
plt.show()

#%%
# Random forest min_samples_split tuning
min_samples_splits = np.linspace(0.025, 1, 40, endpoint=True)

train_results = []
test_results = []

for min_samples_split in min_samples_splits:
    rfc = RandomForestClassifier(class_weight='balanced', n_estimators=500, max_features=0.1, max_depth=7, min_samples_split=min_samples_split, n_jobs=-1)
    rfc.fit(x_train, y_train)
    
    rfc_train = rfc.predict_proba(x_train)
    rfc_train = rfc_train[:,1]
    rfc_auc = roc_auc_score(y_train, rfc_train)
    
    rfc_fpr, rfc_tpr, thresholds = roc_curve(y_train, rfc_train, drop_intermediate=False)
    train_results.append(rfc_auc)

    rfc_test = rfc.predict_proba(x_test)
    rfc_test = rfc_test[:,1]
    rfc_auc = roc_auc_score(y_test, rfc_test)

    rfc_fpr, rfc_tpr, thresholds = roc_curve(y_test, rfc_test, drop_intermediate=False)
    test_results.append(rfc_auc)

line1, = plt.plot(min_samples_splits, train_results, 'b', label='AUC (TRAINING)')
line2, = plt.plot(min_samples_splits, test_results, 'r', label='AUC (TESTING)')
plt.legend(handler_map={line1: HandlerLine2D(numpoints=2)})
plt.ylabel('AUC SCORE')
plt.xlabel('MIN SAMPLES SPLIT')
plt.show()

#%%
# Random forest min_samples_leaf tuning
min_samples_leafs = np.linspace(0.025, 0.5, 20, endpoint=True)

train_results = []
test_results = []

for min_samples_leaf in min_samples_leafs:
    rfc = RandomForestClassifier(class_weight='balanced', n_estimators=500, max_features=0.1, max_depth=7, min_samples_split=0.025, min_samples_leaf=min_samples_leaf, n_jobs=-1)
    rfc.fit(x_train, y_train)
    
    rfc_train = rfc.predict_proba(x_train)
    rfc_train = rfc_train[:,1]
    rfc_auc = roc_auc_score(y_train, rfc_train)
    
    rfc_fpr, rfc_tpr, thresholds = roc_curve(y_train, rfc_train, drop_intermediate=False)
    train_results.append(rfc_auc)

    rfc_test = rfc.predict_proba(x_test)
    rfc_test = rfc_test[:,1]
    rfc_auc = roc_auc_score(y_test, rfc_test)

    rfc_fpr, rfc_tpr, thresholds = roc_curve(y_test, rfc_test, drop_intermediate=False)
    test_results.append(rfc_auc)

line1, = plt.plot(min_samples_leafs, train_results, 'b', label='AUC (TRAINING)')
line2, = plt.plot(min_samples_leafs, test_results, 'r', label='AUC (TESTING)')
plt.legend(handler_map={line1: HandlerLine2D(numpoints=2)})
plt.ylabel('AUC SCORE')
plt.xlabel('MIN SAMPLES LEAF')
plt.show()

#%%
# Random forest model
rfc = RandomForestClassifier(class_weight='balanced', n_estimators=1000, max_features=0.1, max_depth=7, min_samples_split=0.025, min_samples_leaf=0.1)
rfc.fit(x_train, y_train)

rfc_probs = rfc.predict_proba(x_train)
rfc_probs = rfc_probs[:, 1]
rfc_auc = roc_auc_score(y_train, rfc_probs)

print(f'Overall accuracy for random forest model (training): {rfc.score(x_train, y_train):.4f}')
print(f'ROC AUC for random forest model (training): {rfc_auc:.4f}')
print(f'Overall accuracy for random forest model (testing): {rfc.score(x_test, y_test):.4f}')

rfc_fpr, rfc_tpr, thresholds = roc_curve(y_train, rfc_probs, drop_intermediate=False)

plt.plot(rfc_fpr, rfc_tpr, color='red', lw=2, label='ROC CURVE')
plt.plot([0, 1], [0, 1], color='blue', lw=2, linestyle='--')
plt.xlabel('FALSE-POSITIVE RATE (1 - SPECIFICITY)')
plt.ylabel('TRUE-POSITIVE RATE (SENSITIVITY)')
plt.title('RANDOM FOREST ROC CURVE (TRAINING)')
plt.show()

#%%

lreg_pred_probs = lreg.predict_proba(x_test)
lreg_pred_probs = lreg_pred_probs[:, 1]
svc_pred_probs = probs.predict_proba(x_test)
svc_pred_probs = svc_pred_probs[:, 1]
rfc_pred_probs = rfc.predict_proba(x_test)
rfc_pred_probs = rfc_pred_probs[:, 1]

#%%
# Model predictions

pred_outcome['lr_prob'] = pd.DataFrame(lreg_pred_probs)
pred_outcome['lr_pred'] = lreg.predict(x_test)
pred_outcome['svc_prob'] = pd.DataFrame(svc_pred_probs)
pred_outcome['svc_pred'] = svc.predict(x_test)
pred_outcome['rfc_prob'] = pd.DataFrame(rfc_pred_probs)
pred_outcome['rfc_pred'] = rfc.predict(x_test)
pred_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\pred_outcome.csv', encoding='utf-8', index=False)

# %%
