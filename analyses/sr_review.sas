* ----------------------------------------------------------------------------- ;
*                                                                               ;
*                             STUDENT RISK REVIEW                               ;
*                                                                               ;
* ----------------------------------------------------------------------------- ;

libname acs "Z:\Nathan\Models\student_risk\supplemental_files";

proc import out=pullm_frsh_pred_outcome
	datafile="Z:\Nathan\Models\student_risk\predictions\pullm\pullm_frsh_pred_outcome.csv"
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
		case when a.vcf_pred = 0 and a.emplid = input(b.emplid, z9.) 	then 0
																		else 1
																		end as nonenroll_match
	from pullm_frsh_pred_outcome as a
	left join enrollment as b
		on a.emplid = input(b.emplid, z9.)
;quit;

proc sql;
	create table stats as
	select distinct
		sum(enroll_match)/count(enroll_match) as enroll_accuracy,
		sum(nonenroll_match)/count(nonenroll_match) as nonenroll_accuracy
	from return
;quit;

proc print data=stats;
run;
