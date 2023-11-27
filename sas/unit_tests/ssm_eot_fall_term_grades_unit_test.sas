* -------------------------------------------------------------------------------------------- ;
*                                                                                              ;
*                             SSM EOT FALL TERM GRADES UNIT TEST                               ;
*                                                                                              ;
* -------------------------------------------------------------------------------------------- ;

%let dsn = census;
%let adm = adm;
%let acs_lag = 2;
%let lag_year = 1;

libname &dsn. odbc dsn=&dsn. schema=dbo;
libname &adm. odbc dsn=&adm. schema=dbo;

libname acs "Z:\Nathan\Models\student_risk\supplemental_files";

options sqlreduceput=all sqlremerge;
run;

%include "Z:\Nathan\Models\student_risk\sas\unit_tests\ssm_class_registration_unit_test.sas";

%let cohort_year = 2023;

proc sql;
	create table eot_fall_term_grades_&cohort_year. as
	select distinct
		a.emplid,
		b.fall_term_gpa_hours,
		b.fall_term_gpa,
		c.fall_term_D_grade_count,
		c.fall_term_F_grade_count,
		c.fall_term_W_grade_count,
		c.fall_term_I_grade_count,
		c.fall_term_X_grade_count,
		c.fall_term_U_grade_count,
		c.fall_term_S_grade_count,
		c.fall_term_P_grade_count,
		c.fall_term_Z_grade_count,
		c.fall_term_letter_count,
		c.fall_term_grade_count
	from eot_class_registration_&cohort_year. as a
	left join (select distinct
					emplid,
					sum(unt_taken) as fall_term_gpa_hours,
					round(sum(class_gpa * unt_taken) / sum(unt_taken), .01) as fall_term_gpa
				from eot_class_registration_&cohort_year.
				where strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
					and grading_basis_enrl = 'GRD'
					and crse_grade in ('A','A-','B+','B','B-','C+','C','C-','D+','D','F')
				group by emplid) as b
		on a.emplid = b.emplid
	left join (select distinct 
					emplid,
					sum(D_grade_ind) as fall_term_D_grade_count,
					sum(F_grade_ind) as fall_term_F_grade_count,
					sum(W_grade_ind) as fall_term_W_grade_count,
					sum(I_grade_ind) as fall_term_I_grade_count,
					sum(X_grade_ind) as fall_term_X_grade_count,
					sum(U_grade_ind) as fall_term_U_grade_count,
					sum(S_grade_ind) as fall_term_S_grade_count,
					sum(P_grade_ind) as fall_term_P_grade_count,
					sum(Z_grade_ind) as fall_term_Z_grade_count,
					count(class_gpa) as fall_term_letter_count,
					sum(term_grade_ind) as fall_term_grade_count
				from eot_class_registration_&cohort_year.
				where strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
				group by emplid) as c
		on a.emplid = c.emplid
	where a.strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
;quit;
