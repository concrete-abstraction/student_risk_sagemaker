import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import statsmodels as sm
from patsy import dmatrices
from statsmodels.discrete.discrete_model import Logit
from sklearn.compose import make_column_transformer
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder, PolynomialFeatures, StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix, roc_curve, roc_auc_score

training_set = pd.read_csv('Z:/Nathan/Models/student_risk/training_set.csv', encoding='utf-8')
testing_set = pd.read_csv('Z:/Nathan/Models/student_risk/testing_set.csv', encoding='utf-8')

logit_df = training_set[[
                        'enrl_ind', 
                        # 'acad_year',
                        # 'age_group', 
                        'age',
                        'male',
                        # 'marital_status',
                        'Distance',
                        # 'underrep_minority', 
                        'ipeds_ethnic_group_descrshort',
                        'pell_eligibility_ind', 
                        # 'pell_recipient_ind',
                        'first_gen_flag', 
                        # 'LSAMP_STEM_Flag',
                        'anywhere_STEM_Flag',
                        'high_school_gpa', 
                        'cum_adj_transfer_hours',
                        'resident',
                        'father_wsu_flag',
                        'mother_wsu_flag',
                        'parent1_highest_educ_lvl',
                        'parent2_highest_educ_lvl',
                        # 'citizenship_country',
                        'AD_DTA',
                        'AD_AST',
                        'AP',
                        'RS',
                        'CHS',
                        'IB',
                        'AICE', 
                        'term_credit_hours',
                        'athlete',
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
                        'last_sch_proprietorship',
                        'sat_erws',
                        'sat_mss',
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

training_set = training_set[[
                            'emplid',
                            'enrl_ind', 
                            # 'acad_year',
                            # 'age_group', 
                            'age', 
                            'male',
                            # 'marital_status',
                            'Distance',
                            # 'underrep_minority', 
                            'ipeds_ethnic_group_descrshort',
                            'pell_eligibility_ind', 
                            # 'pell_recipient_ind',
                            'first_gen_flag',
                            # 'LSAMP_STEM_Flag',
                            'anywhere_STEM_Flag', 
                            'high_school_gpa', 
                            'cum_adj_transfer_hours',
                            'resident',
                            'father_wsu_flag',
                            'mother_wsu_flag',
                            'parent1_highest_educ_lvl',
                            'parent2_highest_educ_lvl',
                            # 'citizenship_country',
                            'AD_DTA',
                            'AD_AST',
                            'AP',
                            'RS',
                            'CHS',
                            'IB',
                            'AICE', 
                            'term_credit_hours',
                            'athlete',
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
                            'last_sch_proprietorship',
                            'sat_erws',
                            'sat_mss',
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
                            'Distance',
                            # 'underrep_minority', 
                            'ipeds_ethnic_group_descrshort',
                            'pell_eligibility_ind', 
                            # 'pell_recipient_ind',
                            'first_gen_flag',
                            # 'LSAMP_STEM_Flag', 
                            'anywhere_STEM_Flag',
                            'high_school_gpa', 
                            'cum_adj_transfer_hours',
                            'resident',
                            'father_wsu_flag',
                            'mother_wsu_flag',
                            'parent1_highest_educ_lvl',
                            'parent2_highest_educ_lvl',
                            # 'citizenship_country',
                            'AD_DTA',
                            'AD_AST',
                            'AP',
                            'RS',
                            'CHS',
                            'IB',
                            'AICE', 
                            'term_credit_hours',
                            'athlete',
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
                            'last_sch_proprietorship',
                            'sat_erws',
                            'sat_mss',
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
                        'Distance',
                        # 'underrep_minority', 
                        'ipeds_ethnic_group_descrshort',
                        'pell_eligibility_ind', 
                        # 'pell_recipient_ind',
                        'first_gen_flag', 
                        # 'LSAMP_STEM_Flag',
                        'anywhere_STEM_Flag',
                        'high_school_gpa', 
                        'cum_adj_transfer_hours',
                        'resident',
                        'father_wsu_flag',
                        'mother_wsu_flag',
                        'parent1_highest_educ_lvl',
                        'parent2_highest_educ_lvl',
                        # 'citizenship_country',
                        'AD_DTA',
                        'AD_AST',
                        'AP',
                        'RS',
                        'CHS',
                        'IB',
                        'AICE', 
                        'term_credit_hours',
                        'athlete',
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
                        'last_sch_proprietorship',
                        'sat_erws',
                        'sat_mss',
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
                        'Distance',
                        # 'underrep_minority', 
                        'ipeds_ethnic_group_descrshort',
                        'pell_eligibility_ind', 
                        # 'pell_recipient_ind',
                        'first_gen_flag', 
                        # 'LSAMP_STEM_Flag',
                        'anywhere_STEM_Flag',
                        'high_school_gpa', 
                        'cum_adj_transfer_hours',
                        'resident',
                        'father_wsu_flag',
                        'mother_wsu_flag',
                        'parent1_highest_educ_lvl',
                        'parent2_highest_educ_lvl',
                        # 'citizenship_country',
                        'AD_DTA',
                        'AD_AST',
                        'AP',
                        'RS',
                        'CHS',
                        'IB',
                        'AICE', 
                        'term_credit_hours',
                        'athlete',
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
                        'last_sch_proprietorship',
                        'sat_erws',
                        'sat_mss',
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

# x_train.hist(bins=50)
# plt.show()

preprocess = make_column_transformer(
    (MinMaxScaler(), [
                        'age',
                        'sat_erws',
                        'sat_mss',
                        # 'attendee_total_visits',
                        'Distance', 
                        # 'qvalue', 
                        'term_credit_hours',
                        'high_school_gpa', 
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
                                    'last_sch_proprietorship', 
                                    'parent1_highest_educ_lvl',
                                    'parent2_highest_educ_lvl',
                                    ]),
    # (PolynomialFeatures(interaction_only=True), ['male', 'underrep_minority']),
    remainder='passthrough'
)

x_train = preprocess.fit_transform(x_train)
x_test = preprocess.fit_transform(x_test)

y, x = dmatrices('enrl_ind ~ age + male + ipeds_ethnic_group_descrshort + Distance \
                + pell_eligibility_ind + first_gen_flag + anywhere_STEM_Flag + high_school_gpa + cum_adj_transfer_hours \
                + resident + father_wsu_flag + mother_wsu_flag + parent1_highest_educ_lvl \
                + parent2_highest_educ_lvl + AD_DTA + AD_AST + AP + RS + CHS + IB + AICE + term_credit_hours + athlete \
                + cahnrext + cas + comm + education + med_sci + medicine + nursing + pharmacy + provost + vcea + vet_med \
                + last_sch_proprietorship + sat_erws + sat_mss + attendee_any_visitation_ind + fed_efc + fed_need + unmet_need_ofr', data=logit_df, return_type='matrix')

logit_mod = Logit(y, x)
logit_res = logit_mod.fit(maxiter=500)
print(logit_res.summary())

lr = LogisticRegression(penalty='elasticnet', solver='saga', max_iter=500, l1_ratio=.5)
lr.fit(x_train, y_train)

lr_probs = lr.predict_proba(x_train)
lr_probs = lr_probs[:, 1]
lr_auc = roc_auc_score(y_train, lr_probs)

print(f"Overall accuracy for logistic model (training): {lr.score(x_train, y_train):.4f}")
print(f"ROC AUC for logistic model (training): {lr_auc:.4f}")
print(f"Overall accuracy for logistic model (testing): {lr.score(x_test, y_test):.4f}")
print(f"Number of features used in logistic model: {np.sum(lr.coef_ != 0)}")

lr_fpr, lr_tpr, thresholds = roc_curve(y_train, lr_probs, drop_intermediate=False)

plt.plot(lr_fpr, lr_tpr, color='red', lw=2, label='ROC CURVE')
plt.plot([0, 1], [0, 1], color='blue', lw=2, linestyle='--')
plt.xlabel('FALSE-POSITIVE RATE (1 - SPECIFICITY)')
plt.ylabel('TRUE-POSITIVE RATE (SENSITIVITY)')
plt.title('LOGISTIC ROC CURVE (TRAINING)')
plt.show()

svc = SVC(kernel='linear', class_weight='balanced', probability=True)
svc.fit(x_train, y_train)

svc_probs = svc.predict_proba(x_train)
svc_probs = svc_probs[:, 1]
svc_auc = roc_auc_score(y_train, svc_probs)

print(f"Overall accuracy for linear SVC model (training): {svc.score(x_train,y_train):.4f}")
print(f"ROC AUC for linear SVC model (training): {svc_auc:.4f}")
print(f"Overall accuracy for linear SVC model (testing): {svc.score(x_test, y_test):.4f}")
print(f"Number of features used in linear SVC model: {np.sum(svc.coef_ != 0)}")

svc_fpr, svc_tpr, thresholds = roc_curve(y_train, svc_probs, drop_intermediate=False)

plt.plot(svc_fpr, svc_tpr, color='red', lw=2, label='ROC CURVE')
plt.plot([0, 1], [0, 1], color='blue', lw=2, linestyle='--')
plt.xlabel('FALSE-POSITIVE RATE (1 - SPECIFICITY)')
plt.ylabel('TRUE-POSITIVE RATE (SENSITIVITY)')
plt.title('LINEAR SVC ROC CURVE (TRAINING)')
plt.show()

rfc = RandomForestClassifier(class_weight='balanced')
rfc.fit(x_train, y_train)

rfc_probs = rfc.predict_proba(x_train)
rfc_probs = rfc_probs[:, 1]
rfc_auc = roc_auc_score(y_train, rfc_probs)

print(f"Overall accuracy for random forest model (training): {rfc.score(x_train, y_train):.4f}")
print(f"ROC AUC for random forest model (training): {rfc_auc:.4f}")
print(f"Overall accuracy for random forest model (testing): {rfc.score(x_test, y_test):.4f}")

rfc_fpr, rfc_tpr, thresholds = roc_curve(y_train, rfc_probs, drop_intermediate=False)

plt.plot(rfc_fpr, rfc_tpr, color='red', lw=2, label='ROC CURVE')
plt.plot([0, 1], [0, 1], color='blue', lw=2, linestyle='--')
plt.xlabel('FALSE-POSITIVE RATE (1 - SPECIFICITY)')
plt.ylabel('TRUE-POSITIVE RATE (SENSITIVITY)')
plt.title('RANDOM FOREST ROC CURVE (TRAINING)')
plt.show()

pred_outcome['lr pred'] = lr.predict(x_test)
pred_outcome['svc_pred'] = svc.predict(x_test)
pred_outcome['rfc_pred'] = rfc.predict(x_test)
pred_outcome.to_csv('Z:/Nathan/Models/student_risk/pred_outcome.csv', encoding='utf-8', index=False)