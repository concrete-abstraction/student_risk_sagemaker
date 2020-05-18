#%%
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.legend_handler import HandlerLine2D
from patsy import dmatrices
from statsmodels.api import OLS
from statsmodels.discrete.discrete_model import Logit
from statsmodels.stats.outliers_influence import variance_inflation_factor
from sklearn.compose import make_column_transformer
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder, PolynomialFeatures, StandardScaler
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix, roc_curve, roc_auc_score
from sklearn.model_selection import GridSearchCV

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
testing_awe_pred['actual'] = testing_awe['high_school_gpa']
testing_awe_pred['predicted'] = reg.predict(awe_x_test)
testing_awe_pred['awe_instrument'] = testing_awe_pred['actual'] - testing_awe_pred['predicted']

testing_set = testing_set.join(testing_awe_pred.set_index('emplid'), on='emplid')

#%%
# Prepare dataframes
logit_df = training_set[[
                        'enrl_ind', 
                        # 'acad_year',
                        # 'age_group', 
                        'age',
                        'male',
                        # 'marital_status',
                        # 'Distance',
                        # 'pop_dens',
                        'underrep_minority', 
                        # 'ipeds_ethnic_group_descrshort',
                        'pell_eligibility_ind', 
                        # 'pell_recipient_ind',
                        'first_gen_flag', 
                        # 'LSAMP_STEM_Flag',
                        'anywhere_STEM_Flag',
                        # 'high_school_gpa',
                        'awe_instrument',
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
                        'sat_comp',
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
                            # 'marital_status',
                            # 'Distance',
                            # 'pop_dens',
                            # 'underrep_minority', 
                            'ipeds_ethnic_group_descrshort',
                            'pell_eligibility_ind', 
                            # 'pell_recipient_ind',
                            'first_gen_flag',
                            # 'LSAMP_STEM_Flag',
                            'anywhere_STEM_Flag', 
                            # 'high_school_gpa', 
                            'awe_instrument',
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
                            'sat_comp',
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
                            # 'marital_status',
                            # 'Distance',
                            # 'pop_dens',
                            # 'underrep_minority', 
                            'ipeds_ethnic_group_descrshort',
                            'pell_eligibility_ind', 
                            # 'pell_recipient_ind',
                            'first_gen_flag',
                            # 'LSAMP_STEM_Flag', 
                            'anywhere_STEM_Flag',
                            # 'high_school_gpa',
                            'awe_instrument', 
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
                            'sat_comp',
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

pred_outcome = testing_set[[ 
                            'emplid',
                            'enrl_ind'
                            ]].copy(deep=True)

x_train = training_set[[
                        # 'acad_year',
                        # 'age_group', 
                        'age', 
                        'male',
                        # 'marital_status',
                        # 'Distance',
                        # 'pop_dens',
                        # 'underrep_minority', 
                        'ipeds_ethnic_group_descrshort',
                        'pell_eligibility_ind', 
                        # 'pell_recipient_ind',
                        'first_gen_flag', 
                        # 'LSAMP_STEM_Flag',
                        'anywhere_STEM_Flag',
                        # 'high_school_gpa',
                        'awe_instrument', 
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
                        'sat_comp',
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
                        # 'marital_status',
                        # 'Distance',
                        # 'pop_dens',
                        # 'underrep_minority', 
                        'ipeds_ethnic_group_descrshort',
                        'pell_eligibility_ind', 
                        # 'pell_recipient_ind',
                        'first_gen_flag', 
                        # 'LSAMP_STEM_Flag',
                        'anywhere_STEM_Flag',
                        # 'high_school_gpa',
                        'awe_instrument', 
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
                        'sat_comp',
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
# Preprocess data
preprocess = make_column_transformer(
    (MinMaxScaler(), [
                        'age',
                        # 'sat_erws',
                        # 'sat_mss',
                        'sat_comp',
                        # 'attendee_total_visits',
                        # 'Distance',
                        # 'pop_dens', 
                        # 'qvalue', 
                        'median_inc',
                        # 'median_value',
                        'term_credit_hours',
                        # 'high_school_gpa',
                        'awe_instrument',
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
                                    # 'LSAMP_STEM_Flag',
                                    'anywhere_STEM_Flag', 
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
y, x = dmatrices('enrl_ind ~ age + male + underrep_minority + pct_blk + pct_ai + pct_asn + pct_hawi + pct_oth + pct_two + pct_hisp \
                + city_large + city_mid + city_small + suburb_large + suburb_mid + suburb_small \
                + pell_eligibility_ind + first_gen_flag + anywhere_STEM_Flag + awe_instrument + cum_adj_transfer_hours \
                + resident + father_wsu_flag + mother_wsu_flag + parent1_highest_educ_lvl + gini_indx + median_inc + educ_rate \
                + parent2_highest_educ_lvl + AD_DTA + AD_AST + AP + RS + CHS + IB + AICE + term_credit_hours + athlete + remedial \
                + cahnrext + cas + comm + education + med_sci + medicine + nursing + pharmacy + provost + vcea + vet_med \
                + sat_comp + attendee_total_visits + fed_efc + fed_need + unmet_need_ofr', data=logit_df, return_type='dataframe')

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
penalty = ['l1', 'l2']
C = np.logspace(0, 4, 10, endpoint=True)
hyperparameters = dict(penalty=penalty, C=C)

gridsearch = GridSearchCV(LogisticRegression(solver='saga', class_weight='balanced'), hyperparameters, cv=5, verbose=0, n_jobs=-1)
best_model = gridsearch.fit(x_train, y_train)

print(f'Best parameters: {gridsearch.best_params_}')

#%%
# Logistic model
lreg = LogisticRegression(penalty='l1', solver='saga', max_iter=500, C=1.0, n_jobs=-1)
lreg.fit(x_train, y_train)

lreg_probs = lreg.predict_proba(x_train)
lreg_probs = lreg_probs[:, 1]
lreg_auc = roc_auc_score(y_train, lreg_probs)

print(f'Overall accuracy for logistic model (training): {lreg.score(x_train, y_train):.4f}')
print(f'ROC AUC for logistic model (training): {lreg_auc:.4f}')
print(f'Overall accuracy for logistic model (testing): {lreg.score(x_test, y_test):.4f}')
print(f'Number of features used in logistic model: {np.sum(lreg.coef_ != 0)}')

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
                    {'kernel': ['rbf'],
                    'C': np.logspace(0, 4, 5, endpoint=True),
                    'gamma': np.logspace(0, 4, 5, endpoint=True)}]

gridsearch = GridSearchCV(SVC(class_weight='balanced'), hyperparameters, cv=5, verbose=0, n_jobs=-1)
best_model = gridsearch.fit(x_train, y_train)

print(f'Best parameters: {gridsearch.best_params_}')

#%%
# SVC model
svc = SVC(kernel='linear', class_weight='balanced', probability=True)
svc.fit(x_train, y_train)

svc_probs = svc.predict_proba(x_train)
svc_probs = svc_probs[:, 1]
svc_auc = roc_auc_score(y_train, svc_probs)

print(f'Overall accuracy for linear SVC model (training): {svc.score(x_train,y_train):.4f}')
print(f'ROC AUC for linear SVC model (training): {svc_auc:.4f}')
print(f'Overall accuracy for linear SVC model (testing): {svc.score(x_test, y_test):.4f}')
print(f'Number of features used in linear SVC model: {np.sum(svc.coef_ != 0)}')

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
# Random forest min_samples_split tuning
min_samples_splits = np.linspace(0.025, 1, 40, endpoint=True)

train_results = []
test_results = []

for min_samples_split in min_samples_splits:
    rfc = RandomForestClassifier(class_weight='balanced', n_estimators=500, max_features='sqrt', max_depth=16, min_samples_split=min_samples_split, n_jobs=-1)
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
    rfc = RandomForestClassifier(class_weight='balanced', n_estimators=500, max_features='sqrt', max_depth=16, min_samples_split=0.025, min_samples_leaf=min_samples_leaf, n_jobs=-1)
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
rfc = RandomForestClassifier(class_weight='balanced', n_estimators=1000, max_features='sqrt', max_depth=16, min_samples_split=0.025, min_samples_leaf=0.1)
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
# Model predictions
pred_outcome['lr pred'] = lreg.predict(x_test)
pred_outcome['svc_pred'] = svc.predict(x_test)
pred_outcome['rfc_pred'] = rfc.predict(x_test)
pred_outcome.to_csv('Z:\\Nathan\\Models\\student_risk\\pred_outcome.csv', encoding='utf-8', index=False)
