import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import statsmodels as sm
from patsy import dmatrices
from statsmodels.discrete.discrete_model import Logit
from sklearn.compose import make_column_transformer
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder, PolynomialFeatures, StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, roc_curve, roc_auc_score
from logitboost import LogitBoost

training_set = pd.read_csv('Z:/Nathan/Models/student_risk/training_set.csv', encoding='utf-8')
testing_set = pd.read_csv('Z:/Nathan/Models/student_risk/testing_set.csv', encoding='utf-8')

logit_df = training_set[['enrl_ind', 
                        # 'acad_year',
                        'age_group', 
                        # 'age',
                        'male',
                        # 'marital_status',
                        # 'Distance',
                        # 'underrep_minority', 
                        'ipeds_ethnic_group_descrshort',
                        'pell_eligibility_ind', 
                        # 'pell_recipient_ind',
                        'first_gen_flag', 
                        'LSAMP_STEM_Flag',
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
                        # 'qvalue',
                        'fed_efc',
                        'fed_need',
                        'unmet_need_ofr'
                        ]].dropna()

training_set = training_set[['enrl_ind', 
                            # 'acad_year',
                            'age_group', 
                            # 'age', 
                            'male',
                            # 'marital_status',
                            # 'Distance',
                            # 'underrep_minority', 
                            'ipeds_ethnic_group_descrshort',
                            'pell_eligibility_ind', 
                            # 'pell_recipient_ind',
                            'first_gen_flag',
                            'LSAMP_STEM_Flag', 
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
                            # 'qvalue',
                            'fed_efc',
                            'fed_need',
                            'unmet_need_ofr'
                            ]].dropna()

testing_set = testing_set[['enrl_ind', 
                            # 'acad_year',
                            'age_group', 
                            # 'age', 
                            'male',
                            # 'marital_status',
                            # 'Distance',
                            # 'underrep_minority', 
                            'ipeds_ethnic_group_descrshort',
                            'pell_eligibility_ind', 
                            # 'pell_recipient_ind',
                            'first_gen_flag',
                            'LSAMP_STEM_Flag', 
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
                            # 'qvalue',
                            'fed_efc',
                            'fed_need',
                            'unmet_need_ofr'
                            ]].dropna()

x_train = training_set[[# 'acad_year',
                        'age_group', 
                        # 'age', 
                        'male',
                        # 'marital_status',
                        # 'Distance',
                        # 'underrep_minority', 
                        'ipeds_ethnic_group_descrshort',
                        'pell_eligibility_ind', 
                        # 'pell_recipient_ind',
                        'first_gen_flag', 
                        'LSAMP_STEM_Flag',
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
                        # 'qvalue',
                        'fed_efc',
                        'fed_need',
                        'unmet_need_ofr'
                        ]]

x_test = testing_set[[# 'acad_year', 
                        'age_group',
                        # 'age', 
                        'male',
                        # 'marital_status',
                        # 'Distance',
                        # 'underrep_minority', 
                        'ipeds_ethnic_group_descrshort',
                        'pell_eligibility_ind', 
                        # 'pell_recipient_ind',
                        'first_gen_flag', 
                        'LSAMP_STEM_Flag',
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
    (MinMaxScaler(), [# 'age',
                        'sat_erws',
                        'sat_mss',
                        # 'Distance', 
                        # 'qvalue', 
                        'term_credit_hours',
                        'high_school_gpa', 
                        'cum_adj_transfer_hours',
                        'fed_efc',
                        'fed_need', 
                        'unmet_need_ofr'
                        ]),
    (OneHotEncoder(drop='first'), [# 'acad_year', 
                                    'age_group',
                                    # 'marital_status',
                                    'first_gen_flag',
                                    'LSAMP_STEM_Flag', 
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

y, x = dmatrices('enrl_ind ~ age_group + male + ipeds_ethnic_group_descrshort \
                + pell_eligibility_ind + first_gen_flag + LSAMP_STEM_Flag + high_school_gpa + cum_adj_transfer_hours \
                + resident + father_wsu_flag + mother_wsu_flag + parent1_highest_educ_lvl \
                + parent2_highest_educ_lvl + AD_DTA + AD_AST + AP + RS + CHS + IB + AICE + term_credit_hours \
                + cahnrext + cas + comm + education + med_sci + medicine + nursing + pharmacy + provost + vcea + vet_med \
                + last_sch_proprietorship + sat_erws + sat_mss + fed_efc + fed_need + unmet_need_ofr', data=logit_df, return_type='matrix')

logit_mod = Logit(y, x)
logit_res = logit_mod.fit(maxiter=500)
print(logit_res.summary())

# lr = LogitBoost(n_estimators=1000, bootstrap=True, random_state=0)
# lr.fit(x_train, y_train)

lr = LogisticRegression(penalty='elasticnet', solver='saga', max_iter=500, l1_ratio=.25)
lr.fit(x_train, y_train)

print(f"Overall accuracy (training): {lr.score(x_train, y_train):.4f}")

lr_probs = lr.predict_proba(x_train)
lr_probs = lr_probs[:, 1]
lr_auc = roc_auc_score(y_train, lr_probs)
print(f"ROC AUC (training): {lr_auc:.4f}")

print(f"Overall accuracy (testing): {lr.score(x_test, y_test):.4f}")
print(f"Number of features used: {np.sum(lr.coef_ != 0)}")

fpr, tpr, thresholds = roc_curve(y_train, lr_probs, drop_intermediate=False)

plt.plot(fpr, tpr, color='red', lw=2, label='ROC CURVE')
plt.plot([0, 1], [0, 1], color='blue', lw=2, linestyle='--')
plt.xlabel('FALSE-POSITIVE RATE (1 - SPECIFICITY)')
plt.ylabel('TRUE-POSITIVE RATE (SENSITIVITY)')
plt.title('ROC CURVE (TRAINING)')
plt.show()
