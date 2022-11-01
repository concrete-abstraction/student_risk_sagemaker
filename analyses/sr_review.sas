* ----------------------------------------------------------------------------- ;
*                                                                               ;
*                             STUDENT RISK REVIEW                               ;
*                                                                               ;
* ----------------------------------------------------------------------------- ;

libname acs "Z:\Nathan\Models\student_risk\supplemental_files";
libname tableau odbc dsn=oracle_int schema = dbo;

%let strm = 2227;
%let full_acad_year = 2022;

proc sql;
	create table enrollment as 
	select distinct
		emplid
	from acs.crse_grade_data
	where strm = "&strm."
;quit;

proc sql;
	create table return as
	select distinct
		a.emplid,
		a.risk_prob,
		a.date,
		case when a.risk_prob <= .5 and a.emplid = b.emplid				then 1
																		else 0
																		end as enroll_match,
		case when a.risk_prob <= .5 and b.emplid is null				then 1
																		else 0
																		end as enroll_nonmatch,
		case when a.risk_prob > .5 and b.emplid is null				 	then 1
																		else 0
																		end as nonenroll_match,
		case when a.risk_prob > .5 and a.emplid = b.emplid				then 1
																		else 0
																		end as nonenroll_nonmatch
	from (select *, max(date) as max_date from tableau.outcome_archive) as a
	left join enrollment as b	
		on a.emplid = b.emplid
/* 	where date = max_date */
;quit;

proc sql;
	create table stats as
	select distinct
	 	(sum(enroll_match) + sum(nonenroll_match))/(sum(enroll_match) + sum(enroll_nonmatch) + sum(nonenroll_match) + sum(nonenroll_nonmatch)) as overall_accuracy,
		sum(enroll_match)/(sum(enroll_match) + sum(enroll_nonmatch)) as enroll_accuracy,
		sum(enroll_match) as enroll_match,
		sum(enroll_nonmatch) as enroll_nonmatch,
		sum(nonenroll_match)/(sum(nonenroll_match) + sum(nonenroll_nonmatch)) as nonenroll_accuracy,
		sum(nonenroll_match) as nonenroll_match,
		sum(nonenroll_nonmatch) as nonenroll_nonmatch,
		date
	from return
	group by date
	order by date
;quit;

data acs.sr_review_&full_acad_year.;
	set stats;
run;

proc sql;
	create table confusion_matrix as
	select distinct
		sum(enroll_match) as enroll_match_count,
		sum(enroll_nonmatch) as enroll_nonmatch_count,
		sum(nonenroll_nonmatch) as nonenroll_nonmatch_count,
		sum(nonenroll_match) as nonenroll_match_count
	from return
;quit;

proc print data=stats noobs;
run;

proc print data=confusion_matrix noobs;
run;
