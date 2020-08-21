/*
|
| Nightly Run of Datasets for Risk Model
|
|
|
*/

options mlogic mprint merror symbolgen ;

libname census odbc dsn=census schema=dbo;
libname dir "\\po-fs1.ad.wsu.edu\IR\Nathan\Models\student_risk\Supplemental Files";

%INCLUDE "\\po-fs1.ad.wsu.edu\IR\SAS\SAS-process\control\user\jon\determine_WSUNCT1T.sas";
%INCLUDE "\\po-fs1.ad.wsu.edu\IR\SAS\SAS-process\control\erp\determine_WSUNCPRD.sas";
%global curlib;
%global passthru;
%let curlib = WSUNCPRD;
/*%let curlib = WSUNCT1T;*/

%let strm  = 2207;

proc sql;
select aid_year into: aid_year 
from census.xw_term where strm = "&strm." and acad_career = 'UGRD';
quit;

%put &aid_year.;

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

SELECT DISTINCT A.EMPLID, B.SUBJECT, B.CATALOG_NBR,TO_CHAR(sysdate, 'yyyy/mm/dd') systemdate

FROM PS_STDNT_ENRL_VW A, PS_CLASS_TBL B
WHERE ( A.STRM = %bquote('&strm.')
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

SELECT DISTINCT A.EMPLID, A.INSTITUTION, A.AID_YEAR, A.ACAD_CAREER, SUM( A.OFFER_AMOUNT), B.FED_NEED,TO_CHAR(sysdate, 'yyyy/mm/dd') systemdate 
FROM (PS_STDNT_AWARDS A 
LEFT OUTER JOIN  PS_STDNT_AWD_PER B ON  A.EMPLID = B.EMPLID AND A.INSTITUTION = B.INSTITUTION AND A.AID_YEAR = B.AID_YEAR AND B.AWARD_PERIOD = A.AWARD_PERIOD)
WHERE ( A.AID_YEAR = %bquote('&aid_year.') AND A.AWARD_STATUS = 'O' AND A.AWARD_PERIOD = 'A'
AND A.AWARD_PERIOD = 'A' AND A.ACAD_CAREER = 'UGRD')
GROUP BY  A.EMPLID,  A.INSTITUTION,  A.AID_YEAR,  A.ACAD_CAREER,  B.FED_NEED,sysdate


); 
quit;

proc sql; 
%include "&passthru."; 
create table dir.enrl_data as 
select * from connection to oracle 
(

SELECT DISTINCT A.EMPLID, A.ACAD_CAREER, A.STRM, CASE WHEN  A.STDNT_ENRL_STATUS = 'E' THEN 1 ELSE 0 END,TO_CHAR(sysdate, 'yyyy/mm/dd') systemdate 
FROM PS_STDNT_ENRL_VW A
WHERE ( A.STRM = %bquote('&strm.')
AND A.ACAD_CAREER = 'UGRD'
AND A.STDNT_ENRL_STATUS = 'E')



); 
quit;
