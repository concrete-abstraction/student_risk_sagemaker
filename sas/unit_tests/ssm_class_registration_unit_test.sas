* ------------------------------------------------------------------------------------------ ;
*                                                                                            ;
*                             SSM CLASS REGISTRATION UNIT TEST                               ;
*                                                                                            ;
* ------------------------------------------------------------------------------------------ ;

%let dsn = census;
%let adm = adm;
%let acs_lag = 2;
%let lag_year = 1;

libname &dsn. odbc dsn=&dsn. schema=dbo;
libname &adm. odbc dsn=&adm. schema=dbo;

libname acs "Z:\Nathan\Models\student_risk\supplemental_files";

options sqlreduceput=all sqlremerge;
run;

%let cohort_year = 2023;

proc sql;
	create table eot_class_registration_&cohort_year. as
	select distinct
		strm,
		emplid,
		class_nbr,
		crse_id,
		ssr_component,
		unt_taken,
		grading_basis_enrl,
		enrl_status_reason,
		enrl_ind,
		class_grade_points as grade_points,
		class_grade_points_per_unit as grd_pts_per_unit,
		subject_catalog_nbr,
		crse_grade_off as crse_grade,
		case when crse_grade_off = 'A' 	then 4.0
			when crse_grade_off = 'A-'	then 3.7
			when crse_grade_off = 'B+'	then 3.3
			when crse_grade_off = 'B'	then 3.0
			when crse_grade_off = 'B-'	then 2.7
			when crse_grade_off = 'C+'	then 2.3
			when crse_grade_off = 'C'	then 2.0
			when crse_grade_off = 'C-'	then 1.7
			when crse_grade_off = 'D+'	then 1.3
			when crse_grade_off = 'D'	then 1.0
			when crse_grade_off = 'F'	then 0.0
										else .
										end as class_gpa,
		case when crse_grade_off = 'D' 	then 1
										else 0
										end as D_grade_ind,
		case when crse_grade_off = 'F' 	then 1
										else 0
										end as F_grade_ind,
		case when crse_grade_off = 'W' 	then 1
										else 0
										end as W_grade_ind,
		case when crse_grade_off = 'I' 	then 1
										else 0
										end as I_grade_ind,
		case when crse_grade_off = 'X' 	then 1
										else 0
										end as X_grade_ind,
		case when crse_grade_off = 'U' 	then 1
										else 0
										end as U_grade_ind,
		case when crse_grade_off = 'S' 	then 1
										else 0
										end as S_grade_ind,
		case when crse_grade_off = 'P' 	then 1
										else 0
										end as P_grade_ind,
		case when crse_grade_input = 'Z'	then 1
											else 0
											end as Z_grade_ind,
		case when unt_taken is not null and enrl_status_reason ^= 'WDRW'	then 1
																			else 0
																			end as term_grade_ind
	from &dsn..class_registration_vw
	where snapshot = 'eot'
		and full_acad_year = "&cohort_year."
		and subject_catalog_nbr ^= 'NURS 399'
		and stdnt_enrl_status = 'E'
;quit;
