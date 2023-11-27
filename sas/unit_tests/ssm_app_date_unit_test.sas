* ---------------------------------------------------------------------------------------- ;
*                                                                                          ;
*                             SSM APPLICATION DATE UNIT TEST                               ;
*                                                                                          ;
* ---------------------------------------------------------------------------------------- ;

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
	create table date_&cohort_year. as
	select distinct
		emplid,
		min(week_from_term_begin_dt) as min_week_from_term_begin_dt,
		max(week_from_term_begin_dt) as max_week_from_term_begin_dt,
		count(week_from_term_begin_dt) as count_week_from_term_begin_dt
	from &adm..UGRD_shortened_vw
	where strm = substr(put(%eval(&cohort_year. - &lag_year.), 4.), 1, 1) || substr(put(%eval(&cohort_year. - &lag_year.), 4.), 3, 2) || '7'
		and ugrd_applicant_counting_ind = 1
	group by emplid
;quit;
