* ----------------------------------------------------------------------------- ;
*                                                                               ;
*                             STUDENT RISK REVIEW                               ;
*                                                                               ;
* ----------------------------------------------------------------------------- ;

libname acs "Z:\Nathan\Models\student_risk\supplemental_files";

proc import out=pullm_frsh_pred_outcome
	datafile="Z:\Nathan\Models\student_risk\analyses\pullm_frsh_pred_outcome.csv"
	dbms=CSV REPLACE;
	getnames=YES;
run;

proc import out=vanco_frsh_pred_outcome
	datafile="Z:\Nathan\Models\student_risk\analyses\vanco_frsh_pred_outcome.csv"
	dbms=CSV REPLACE;
	getnames=YES;
run;

proc import out=trici_frsh_pred_outcome
	datafile="Z:\Nathan\Models\student_risk\analyses\trici_frsh_pred_outcome.csv"
	dbms=CSV REPLACE;
	getnames=YES;
run;

proc import out=univr_frsh_pred_outcome
	datafile="Z:\Nathan\Models\student_risk\analyses\univr_frsh_pred_outcome.csv"
	dbms=CSV REPLACE;
	getnames=YES;
run;

proc import out=pullm_tran_pred_outcome
	datafile="Z:\Nathan\Models\student_risk\analyses\pullm_tran_pred_outcome.csv"
	dbms=CSV REPLACE;
	getnames=YES;
run;

proc import out=vanco_tran_pred_outcome
	datafile="Z:\Nathan\Models\student_risk\analyses\vanco_tran_pred_outcome.csv"
	dbms=CSV REPLACE;
	getnames=YES;
run;

proc import out=trici_tran_pred_outcome
	datafile="Z:\Nathan\Models\student_risk\analyses\trici_tran_pred_outcome.csv"
	dbms=CSV REPLACE;
	getnames=YES;
run;

proc import out=univr_tran_pred_outcome
	datafile="Z:\Nathan\Models\student_risk\analyses\univr_tran_pred_outcome.csv"
	dbms=CSV REPLACE;
	getnames=YES;
run;

proc sql;
	create table enrollment as 
	select distinct
		emplid
	from acs.crse_grade_data
	where strm = '2217'
;quit;

proc sql;
	create table return as
	select distinct
		a.emplid,
		a.vcf_pred,
		case when a.vcf_pred = 1 and a.emplid = input(b.emplid, z9.)	then 1
																		else 0
																		end as enroll_match,
		case when a.vcf_pred = 1 and b.emplid is null					then 1
																		else 0
																		end as enroll_nonmatch,
		case when a.vcf_pred = 0 and b.emplid is null				 	then 1
																		else 0
																		end as nonenroll_match,
		case when a.vcf_pred = 0 and a.emplid = input(b.emplid, z9.)	then 1
																		else 0
																		end as nonenroll_nonmatch

/* Freshman models */

	from pullm_frsh_pred_outcome as a
/* 	from vanco_frsh_pred_outcome as a */
/* 	from trici_frsh_pred_outcome as a */
/* 	from univr_frsh_pred_outcome as a */

/* Transfer models */

/* 	from pullm_tran_pred_outcome as a */
/* 	from vanco_tran_pred_outcome as a */
/* 	from trici_tran_pred_outcome as a */
/* 	from univr_tran_pred_outcome as a */

	left join enrollment as b
		on a.emplid = input(b.emplid, z9.)
;quit;

proc sql;
	create table stats as
	select distinct
	 	(sum(enroll_match) + sum(nonenroll_match))/(sum(enroll_match) + sum(enroll_nonmatch) + sum(nonenroll_match) + sum(nonenroll_nonmatch)) as overall_accuracy,
		sum(enroll_match)/(sum(enroll_match) + sum(enroll_nonmatch)) as enroll_accuracy,
		sum(nonenroll_match)/(sum(nonenroll_match) + sum(nonenroll_nonmatch)) as nonenroll_accuracy
	from return
;quit;

proc sql;
	create table confusion_matrix as
	select distinct
		sum(enroll_match) as enroll_match_count,
		sum(enroll_nonmatch) as enroll_nonmatch_count,
		sum(nonenroll_match) as nonenroll_match_count,
		sum(nonenroll_nonmatch) as nonenroll_nonmatch_count
	from return
;quit;

proc print data=stats noobs;
run;

proc print data=confusion_matrix noobs;
run;