* ------------------------------------------------------------------------------------------ ;
*                                                                                            ;
*                             SSM ENROLLED INDICATOR UNIT TEST                               ;
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
	create table enrolled_&cohort_year. as
	select distinct 
		a.emplid, 
		b.cont_term,
		c.grad_term,
		case when c.emplid is not null	then 1
										else 0
										end as deg_ind,
		case when b.emplid is not null 	then 1
			when c.emplid is not null	then 1
										else 0
										end as enrl_ind
	from &dsn..student_enrolled_vw as a
	full join (select distinct 
					emplid 
					,term_code as cont_term
					,enrl_ind
				from &dsn..student_enrolled_vw 
				where snapshot = 'census'
					and full_acad_year = put(%eval(&cohort_year. + &lag_year.), 4.)
					and substr(strm,4,1) = '7'
					and acad_career = 'UGRD'
					and new_continue_status = 'CTU'
					and term_credit_hours > 0) as b
		on a.emplid = b.emplid
	full join (select distinct 
					emplid
					,term_code as grad_term
				from &dsn..student_degree_vw 
				where snapshot = 'degree'
					and put(&cohort_year., 4.) <= full_acad_year <= put(%eval(&cohort_year. + &lag_year.), 4.)
					and acad_career = 'UGRD'
					and ipeds_award_lvl = 5) as c
		on a.emplid = c.emplid
	where a.snapshot = 'census'
		and a.full_acad_year = "&cohort_year."
		and substr(a.strm,4,1) = '7'
		and a.acad_career = 'UGRD'
		and a.term_credit_hours > 0
;quit;
