/*
|
| Nightly Run of Datasets for Risk Model
|
|
|
*/

options mlogic mprint merror symbolgen ;

libname census odbc dsn=census schema=dbo;
libname dir "\\ad.wsu.edu\POIS\IR\Nathan\Models\student_risk\supplemental_files";

%INCLUDE "\\ad.wsu.edu\POIS\IR\SAS\SAS-process\control\user\jon\determine_WSUNCT1T.sas";
%INCLUDE "\\ad.wsu.edu\POIS\IR\SAS\SAS-process\control\erp\determine_WSUNCPRD.sas";
%global curlib;
%global passthru;
%let curlib = WSUNCPRD;
/*%let curlib = WSUNCT1T;*/

proc sql;
	select strm
	into: strm 
	from census.xw_term 
	where term_year = year(today()) 
		and acad_career = 'UGRD' 
		and term_type = (case when today() lt input(catx('/','07','01',put(year(today()),z4.)), mmddyy10.) then 'SPR' else 'FAL' end)
;quit;

proc sql;
	create table strms as
	select strm 
	from census.xw_term 
	where acad_career = 'UGRD' 
		and substr(strm,4,1) in ('7','3')
		and strm between (select max(strm)  
							from census.xw_term 
							where strm < "&strm." 
								and acad_career = 'UGRD' 
								and substr(strm,4,1) in ('7','3')) 
		and (select min(strm) 
				from census.xw_term 
				where strm > "&strm."  
					and acad_career = 'UGRD' 
					and substr(strm,4,1) in ('7','3'))
;quit;

proc sql noprint;
	select distinct 
	strm into: list_of_strms
	separated by "','"
	from strms
;quit;

proc sql;
	create table aid_years as
	select aid_year
	from census.xw_term 
	where acad_career = 'UGRD'
				and substr(strm,4,1) in ('7','3')
		and strm between (select max(strm)  
							from census.xw_term 
							where strm < "&strm." 
								and acad_career = 'UGRD' 
								and substr(strm,4,1) in ('7','3')) 
		and (select min(strm) 
				from census.xw_term 
				where strm > "&strm."  
					and acad_career = 'UGRD' 
					and substr(strm,4,1) in ('7','3'))
;quit;

proc sql noprint;
	select distinct 
	aid_year into: list_of_aid_years
	separated by "','"
	from aid_years
;quit;

%macro passthrulib;
%if &curlib. = WSUNCPRD %then %do;
		%let passthru = 'Z:\SAS\SAS-process\control\erp\determine_WSUNCPRD_pass_through.sas';
	%end;
%else %do;
		%let passthru = 'Z:\SAS\SAS-process\control\user\jon\determine_WSUNCT1T_pass_through.sas';
	%end;
%mend passthrulib;

%passthrulib;
%put &passthru.;

proc sql; 
%include "&passthru."; 
create table dir.subcatnbr_data as 
select * from connection to oracle 
(

SELECT DISTINCT A.STRM, A.EMPLID, B.SUBJECT, B.CATALOG_NBR, B.SSR_COMPONENT, B.CRSE_ID, B.CLASS_NBR, A.UNT_TAKEN, TO_CHAR(sysdate, 'yyyy/mm/dd') systemdate
FROM PS_STDNT_ENRL A, PS_CLASS_TBL B
WHERE (A.STRM >= %bquote('&strm.')
AND A.STDNT_ENRL_STATUS = 'E'
AND A.ACAD_CAREER = 'UGRD'
AND A.ACAD_CAREER = B.ACAD_CAREER
AND A.INSTITUTION = B.INSTITUTION
AND A.STRM = B.STRM
AND A.CLASS_NBR = B.CLASS_NBR)

); 
quit;

proc sql; 
%include "&passthru."; 
create table dir.finaid_data as 
select * from connection to oracle 
(
SELECT  A.EMPLID, A.INSTITUTION, A.AID_YEAR,A.AWARD_PERIOD, A.ACAD_CAREER, SUM(A.OFFER_AMOUNT) AS TOTAL_OFFER, B.FED_NEED, TO_CHAR(sysdate, 'yyyy/mm/dd') systemdate 


FROM PS_STDNT_AWARDS A 
LEFT OUTER JOIN  PS_STDNT_AWD_PER B ON  A.EMPLID = B.EMPLID AND A.INSTITUTION = B.INSTITUTION AND A.AID_YEAR = B.AID_YEAR AND B.AWARD_PERIOD = A.AWARD_PERIOD
WHERE (A.AID_YEAR in %bquote(('&list_of_aid_years.'))  AND A.AWARD_STATUS in ('O','A') AND A.AWARD_PERIOD in ('A','B') AND A.ACAD_CAREER = 'UGRD' )
GROUP BY  A.EMPLID,  A.INSTITUTION,  A.AID_YEAR, A.AWARD_PERIOD, A.ACAD_CAREER
,  B.FED_NEED
, sysdate

); 
quit;


proc sql; 
%include "&passthru."; 
create table dir.enrl_data as 
select * from connection to oracle 
(

SELECT DISTINCT A.EMPLID, A.ACAD_CAREER, A.STRM, CASE WHEN A.STDNT_ENRL_STATUS = 'E' THEN 1 ELSE 0 END AS ENRL_IND, TO_CHAR(sysdate, 'yyyy/mm/dd') systemdate 
FROM PS_STDNT_ENRL_VW A
WHERE (a.strm  in %bquote(('&list_of_strms.'))
AND A.ACAD_CAREER = 'UGRD'
AND A.STDNT_ENRL_STATUS = 'E')

); 
quit;

proc sql; 
%include "&passthru."; 
create table dir.crse_grade_data as 
select * from connection to oracle 
(
SELECT A.EMPLID
				,A.ACAD_CAREER
				,A.STRM
				,A.CLASS_NBR
				,A.UNT_TAKEN
				,B.CRSE_ID
				,B.SUBJECT
				,B.CATALOG_NBR
				,B.SSR_COMPONENT
				,a.GRADING_BASIS_ENRL
				,A.STDNT_ENRL_STATUS
				,A.ENRL_STATUS_REASON
				,A.ENRL_ACTN_RSN_LAST
				,A.CRSE_GRADE_OFF
				,A.GRADE_POINTS
				,A.GRD_PTS_PER_UNIT
				,A.CRSE_GRADE_INPUT
				,C.CRSE_GRADE_INPUT as CRSE_GRADE_INPUT_MID
				,d.CRSE_GRADE_INPUT as CRSE_GRADE_INPUT_FIN
  FROM PS_STDNT_ENRL A 
  LEFT OUTER JOIN  PS_CLASS_TBL B 
  ON  A.INSTITUTION = B.INSTITUTION AND A.STRM = B.STRM AND A.CLASS_NBR = B.CLASS_NBR AND B.SESSION_CODE = A.SESSION_CODE 
  LEFT OUTER JOIN  (select  a1.emplid, a1.strm, a1.class_nbr,a1.CRSE_GRADE_INPUT  from PS_GRADE_ROSTER a1 
  										inner join ps_grade_rstr_type b1
										on a1.strm = b1.strm and a1.class_nbr = b1.class_nbr and a1.grd_rstr_type_seq = b1.GRD_RSTR_TYPE_SEQ AND b1.GRADE_ROSTER_TYPE = 'MID' 
										) c
				ON  A.EMPLID = C.EMPLID AND  A.STRM = C.STRM AND A.CLASS_NBR = C.CLASS_NBR 
  LEFT OUTER JOIN  (select  a1.emplid, a1.strm, a1.class_nbr,a1.CRSE_GRADE_INPUT  from PS_GRADE_ROSTER a1 
  										inner join ps_grade_rstr_type b1
										on a1.strm = b1.strm and a1.class_nbr = b1.class_nbr and a1.grd_rstr_type_seq = b1.GRD_RSTR_TYPE_SEQ AND b1.GRADE_ROSTER_TYPE = 'FIN' 
										) d
				ON  A.EMPLID = d.EMPLID AND  A.STRM = d.STRM AND A.CLASS_NBR = d.CLASS_NBR 
  WHERE  A.ACAD_CAREER = 'UGRD'
     AND a.strm  in %bquote(('&list_of_strms.'))
)
;quit;
