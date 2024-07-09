* ---------------------------------------------------------------------------------------- ;
*                                                                                          ;
*                             SSM ADJUSTED XW TERM UNIT TEST                               ;
*                                                                                          ;
* ---------------------------------------------------------------------------------------- ;

%let dsn = census;
%let adm = adm;

libname &dsn. odbc dsn=&dsn. schema=dbo;
libname &adm. odbc dsn=&adm. schema=dbo;

libname acs "Z:\Nathan\Models\student_risk\supplemental_files";

options sqlreduceput=all sqlremerge;
run;

proc sort data=adm.xw_term out=work.xw_term;
	by acad_career strm;
run;

data work.xw_term;
	set work.xw_term;
	by acad_career;
	if first.acad_career then idx = 1;
	else idx + 1;
	where acad_career = 'UGRD';
run;

proc sql;
	create table acs.adj_term as
	select
		base.acad_career,
		base.term_year,
        base.term_type,
        base.strm,
		base.full_acad_year,
		datepart(base.term_begin_dt) as term_begin_dt format=mmddyyd10.,
		day(datepart(base.term_begin_dt)) as begin_day,
		week(datepart(base.term_begin_dt)) as begin_week,
		month(datepart(base.term_begin_dt)) as begin_month,
		year(datepart(base.term_begin_dt)) as begin_year,
		datepart(base.term_census_dt) as term_census_dt format=mmddyyd10.,
        day(datepart(base.term_census_dt)) as census_day,
		week(datepart(base.term_census_dt)) as census_week,
		month(datepart(base.term_census_dt)) as census_month,
		year(datepart(base.term_census_dt)) as census_year,
		datepart(base.term_midterm_dt) as term_midterm_dt format=mmddyyd10.,
        day(datepart(base.term_midterm_dt)) as midterm_day,
        week(datepart(base.term_midterm_dt)) as midterm_week,
        month(datepart(base.term_midterm_dt)) as midterm_month,
        year(datepart(base.term_midterm_dt)) as midterm_year,
		datepart(base.term_end_dt) as term_eot_dt format=mmddyyd10.,
        day(datepart(base.term_end_dt)) as eot_day,
        week(datepart(base.term_end_dt)) as eot_week,
        month(datepart(base.term_end_dt)) as eot_month,
        year(datepart(base.term_end_dt)) as eot_year,
        coalesce(datepart(intnx('dtday', next.term_begin_dt, -1)),99999) as term_end_dt format=mmddyyd10.,
		coalesce(day(datepart(intnx('dtday', next.term_begin_dt, -1))),99999) as end_day,
		coalesce(week(datepart(intnx('dtday', next.term_begin_dt, -1))),99999) as end_week,
		coalesce(month(datepart(intnx('dtday', next.term_begin_dt, -1))),99999) as end_month,
		coalesce(year(datepart(intnx('dtday', next.term_begin_dt, -1))),99999) as end_year
	from work.xw_term as base
	left join work.xw_term as next
		on base.acad_career = next.acad_career
			and base.idx = next.idx - 1
;quit;
