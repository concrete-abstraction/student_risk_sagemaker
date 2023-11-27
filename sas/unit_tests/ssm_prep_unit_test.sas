* ----------------------------------------------------------------------------------- ;
*                                                                                     ;
*                             SSM PREPARATORY UNIT TEST                               ;
*                                                                                     ;
* ----------------------------------------------------------------------------------- ;

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
	create table preparatory_&cohort_year. as
	select distinct
		emplid,
		ext_subject_area,
		1 as ind
	from &dsn..student_ext_acad_subj
	where snapshot = 'census'
		and ext_subject_area in ('CHS','RS','AP','IB','AICE')
	union
	select distinct
		emplid,
		'RS' as ext_subject_area,
		 1 as ind
	from &dsn..student_acad_prog_plan_vw
	where snapshot = 'census'
		and tuition_group in ('1RS','1TRS')
	order by emplid
;quit;

proc transpose data=preparatory_&cohort_year. let out=preparatory_&cohort_year. (drop=_name_);
	by emplid;
	id ext_subject_area;
run;
