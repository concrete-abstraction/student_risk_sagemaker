/*
|
| Nightly Run of Datasets for Risk Model
|
*/
/* syscc error code can be reset manually */
%let syscc=0;
%let status_cd=&syscc.;
%PUT "******* status of the job is: &status_cd. *****";

%global IR_FS; %let ir_fs=\\ad.wsu.edu\POIS\IR; %put &ir_fs.;
%INCLUDE "&ir_fs.\SAS\Global_Macros\xd_file_update_macros.sas";

options mlogic mprint merror symbolgen ;

libname census odbc dsn=census schema=dbo;
libname UD_t_o_i odbc dsn=UDtabsql_or_int schema=dbo;

libname dir "&ir_fs.\Nathan\Models\student_risk\supplemental_files";
/**/
/*%INCLUDE "\\ad.wsu.edu\POIS\IR\SAS\SAS-process\control\user\jon\determine_WSUNCT1T.sas";*/
%INCLUDE "&ir_fs.\SAS\SAS-process\control\erp\determine_WSUNCPRD.sas";
%INCLUDE "&ir_fs.\SAS\SAS-process\control\sql\determine_oracle_int_prod.sas";

/* Monitor if this will work in batch job if not do not stress about it, just comment it out */
/* if works keep at the end of the program, and update to 'ir.tech@wsu.edu'. */
options emailsys=smtp emailhost=smtp.wsu.edu emailport=25;
proc options group=email;
run;
/* check for errors now */
%let status_cd=&syscc.;
%PUT "******* status of the job is: &status_cd. *****";

%macro fdate(fmt);
   %global tdate;
   data _null_;
      call symput("tdate",left(put(datetime(),&fmt)));
   run;
%mend fdate;

/* set program name for email if needed. */
%macro pname;
   %global pgmname;
   %let pgmname=;

   data _null_;
      set sashelp.vextfl;
      if (substr(fileref,1,3)='_LN' or substr
         (fileref,1,3)='#LN' or substr(fileref,1,3)='SYS') and
         index(upcase(xpath),'.SAS')>0 then do;
         call symput("pgmname",trim(xpath));
         stop;
      end;
   run;
%mend pname;
%pname;
%put "&pgmname.";

/* check for errors now */
%let status_cd=&syscc.;
%PUT "******* status of the job is: &status_cd. *****";

%let emails = "ir.tech@wsu.edu" "nathan.lindstedt@wsu.edu";
/* testing, help stop spamming other staff */
/*%let emails = "keith.m.johnson@wsu.edu";*/

	/* send email good status */
%macro send_mail_g;
	/* set current datetime */
   %fdate(datetime22.3);
	FILENAME Mailbox EMAIL to = (&emails) from = "ir.tech@wsu.edu" Subject="Check for: Nightly Run of Datasets for Risk Model, on: &tdate";
		data _null_;
			file Mailbox;
			put "The job ran to completion, without errors. Code: &syscc.";
			put "Program: &pgmname..";
			put "Processing date/time was: &tdate.";
			put "Check session log files for more information.";
			put '\\ad.wsu.edu\POIS\IR\Nathan\Models\student_risk\supplemental_files\log\';
			put "End:";
		run;
%mend send_mail_g;
	/* send email bad status */
%macro send_mail_b1;
	/* set current datetime */
	%fdate(datetime22.3);
	FILENAME Mailbox EMAIL to = (&emails) from = "ir.tech@wsu.edu" Subject="Check for: Nightly Run of Datasets for Risk Model, on: &tdate";
	DATA _NULL_;
	FILE Mailbox;
	put "An ERROR has occurred in the program: &pgmname..";
	put "At least one table does not exist in work libname space";
	put "List tables and counts at this time.";
	put "table: &table_name1. count: &cnt1.";
	put "table: &table_name2. count: &cnt2.";
	put "table: &table_name3. count: &cnt3.";
	put "table: &table_name4. count: &cnt4.";
	put "Error date/time was: &tdate.";
	put "Check session log files for more information.";
	put '\\ad.wsu.edu\POIS\IR\Nathan\Models\student_risk\supplemental_files\log\';
		put "End:";
	RUN;
%mend send_mail_b1;
%macro send_mail_b2;
	/* set current datetime */
	%fdate(datetime22.3);
	FILENAME Mailbox EMAIL to = (&emails) from = "ir.tech@wsu.edu" Subject="Check for: Nightly Run of Datasets for Risk Model, on: &tdate";
	DATA _NULL_;
	FILE Mailbox;
	put "An ERROR has occurred in the program: &pgmname..";
	put "At least one table have at least 0 obs in work libname space.";
	put "List tables and counts at this time.";
	put "table: &table_name1. count: &cnt1.";
	put "table: &table_name2. count: &cnt2.";
	put "table: &table_name3. count: &cnt3.";
	put "table: &table_name4. count: &cnt4.";
	put "Error date/time was: &tdate.";
	put "Error date/time was: &tdate.";
	put "Check session log files for more information.";
	put '\\ad.wsu.edu\POIS\IR\Nathan\Models\student_risk\supplemental_files\log\';
	put "End:";
	RUN;
%mend send_mail_b2;


%global curlib;
%global passthru;
%let curlib = WSUNCPRD;
%put &curlib.;

/* check for errors now */
%let status_cd=&syscc.;
%PUT "******* status of the job is: &status_cd. *****";

/*%let curlib = WSUNCT1T;*/
proc sql;
create table xw_term1 as
select 
	distinct
	a.strm,
	a.acad_career,
	a.session_code,
	floor((input(strm,8.)+ 18000)/10)*10 + (input(substr(strm,4,1),1.)-1)/2 as term_code,
	floor(calculated term_code/10) as term_year,
	case when substr(a.strm,4,1) = '3' then 'SPR'
		 when substr(a.strm,4,1) = '5' then 'SUM'
		 when substr(a.strm,4,1) = '7' then 'FAL'
		 when substr(a.strm,4,1) = '9' then 'WNT'
		 							   else ' '
									   end as term_type length=3,
	a.descr as term_descr,
	tranwrd(tranwrd(tranwrd(a.descr,' Semester',''),' Session',''),' Term','')  as term_descr15 length=15,

	case when a.acad_career <> 'MEDS' and substr(a.strm,4,1)='5' then ' ' else a.acad_year end as acad_year length=4,
	put(floor((calculated term_code+7)/10),4.) as full_acad_year length=4,
	floor((calculated term_code+8)/10) as fiscal_year,
/*	put(floor((calculated term_code+7)/10),4.) as aid_year length=4,*/
	a.weeks_of_instruct,
	a.term_begin_dt
/*	dhms(intnx('Day',datepart(a.term_begin_dt),11),0,0,0) as term_census_dt format=datetime20.,*/
/*	dhms(intnx('Day',datepart(a.term_begin_dt),29),0,0,0) as term_30th_dt format=datetime20.,*/
/*	dhms(intnx('Day',datepart(a.SSR_TRMAC_LAST_DT),11),0,0,0) as term_max_prog_effdt format=datetime20.,*/
/*	case when a.acad_career = 'MEDS' then . else dhms(datepart("&mid_term_dt."dt),0,0,0) end as term_midterm_dt format=datetime20.,*/
/*	a.term_end_dt,*/
/*	case when a.acad_career = 'MEDS' then dhms(datepart("&term_end_snapshot_dt_meds."dt),0,0,0)*/
/*									 else dhms(datepart("&term_end_snapshot_dt_othr."dt),0,0,0) 	  */
/*									 end as term_end_snapshot_dt format=datetime20.*/
from &curlib..ps_term_tbl  a
where strm >= '2217' ;
quit;

/* check for errors now */
%let status_cd=&syscc.;
%PUT "******* status of the job is: &status_cd. *****";

proc sql noprint;
	select strm
	into: strm 
	from xw_term1
	where term_year = year(today()) 
		and acad_career = 'UGRD' 
		and term_type = (case when today() lt input(catx('/','07','01',put(year(today()),z4.)), mmddyy10.) then 'SPR' else 'FAL' end)
;quit;
%put &strm.;

/* check for errors now */
%let status_cd=&syscc.;
%PUT "******* status of the job is: &status_cd. *****";

/*Need to move to one strm earlier (so a total of four terms). Code was getting preceding and following strm. Need two preceding.*/
proc sql;
	select strm
	into: strmprevious 
	from xw_term1
	where strm = (select max(strm)  
							from xw_term1
							where strm < "&strm." 
								and acad_career = 'UGRD' 
								and substr(strm,4,1) in ('7','3'))
							and acad_career = 'UGRD'
;quit; %put "strmprevious: &strmprevious.";

/* check for errors now */
%let status_cd=&syscc.;
%PUT "******* status of the job is: &status_cd. *****";

proc sql;
	create table strms as
	select strm 
	from xw_term1
	where acad_career = 'UGRD' 
		and substr(strm,4,1) in ('7','3')
		and strm between (select max(strm)  
							from xw_term1
							where strm < "&strmprevious." 
								and acad_career = 'UGRD' 
								and substr(strm,4,1) in ('7','3')) 
		and (select min(strm) 
				from xw_term1
				where strm > "&strm."  
					and acad_career = 'UGRD' 
					and substr(strm,4,1) in ('7','3'))
;quit;
/* proc print data = strms;run; */
/* check for errors now */
%let status_cd=&syscc.;
%PUT "******* status of the job is: &status_cd. *****";

proc sql noprint;
	select distinct 
	strm into: list_of_strms
	separated by "','"
	from strms
;quit;
%put %bquote(('&list_of_strms.'));

/* check for errors now */
%let status_cd=&syscc.;
%PUT "******* status of the job is: &status_cd. *****";

proc sql;
	create table aid_years as
	select distinct a.aid_year
	from &curlib..ps_aid_yr_car_term a
	where a.acad_career = 'UGRD'
				and substr(strm,4,1) in ('7','3')
		and strm between (select max(strm)  
							from &curlib..ps_aid_yr_car_term 
							where strm < "&strm." 
								and acad_career = 'UGRD' 
								and substr(strm,4,1) in ('7','3')) 
		and (select min(strm) 
				from  &curlib..ps_aid_yr_car_term 
				where strm > "&strm."  
					and acad_career = 'UGRD' 
					and substr(strm,4,1) in ('7','3'))
;quit;
/* proc print data = aid_years;run; */
/* check for errors now */
%let status_cd=&syscc.;
%PUT "******* status of the job is: &status_cd. *****";

proc sql noprint;
	select distinct 
	aid_year into: list_of_aid_years
	separated by "','"
	from aid_years
;quit;
%put %bquote(('&list_of_aid_years.'));
/* check for errors now */
%let status_cd=&syscc.;
%PUT "******* status of the job is: &status_cd. *****";

%macro passthrulib;
%if &curlib. = WSUNCPRD %then %do;
		%let passthru = %bquote('&ir_fs.\SAS\SAS-process\control\erp\determine_WSUNCPRD_pass_through.sas');
	%end;
%else %do;
		%let passthru = %bquote('&ir_fs.\SAS\SAS-process\control\user\jon\determine_WSUNCT1T_pass_through.sas');
	%end;
%mend passthrulib;

%passthrulib;
%put &passthru.;
/* check for errors now */
%let status_cd=&syscc.;
%PUT "******* status of the job is: &status_cd. *****";

%let my_data4=crse_grade_data; %put &my_data4.;
%let my_data3=enrl_data; %put &my_data3.;
%let my_data2=finaid_data; %put &my_data2.;
%let my_data1=subcatnbr_data; %put &my_data1.;
/* check for errors now */
%let status_cd=&syscc.;
%PUT "******* status of the job is: &status_cd. *****";

proc sql; 
%include "&passthru."; 
create table subcatnbr_data as 
select * from connection to oracle 
(
SELECT DISTINCT A.STRM, A.EMPLID, B.SUBJECT, B.CATALOG_NBR, B.SSR_COMPONENT, B.CRSE_ID, B.CLASS_NBR, A.UNT_TAKEN, TO_CHAR(sysdate, 'yyyy/mm/dd') systemdate
FROM PS_STDNT_ENRL A, PS_CLASS_TBL B
WHERE a.strm  in %bquote(('&list_of_strms.'))
AND A.STDNT_ENRL_STATUS = 'E'
AND A.ACAD_CAREER = 'UGRD'
AND A.ACAD_CAREER = B.ACAD_CAREER
AND A.INSTITUTION = B.INSTITUTION
AND A.STRM = B.STRM
AND A.CLASS_NBR = B.CLASS_NBR
); quit;

/* check for errors now */
%let status_cd=&syscc.;
%PUT "******* status of the job is: &status_cd. *****";

proc sql; 
%include "&passthru."; 
create table &my_data2. as 
select * from connection to oracle 
(
SELECT  A.EMPLID, A.INSTITUTION, A.AID_YEAR,A.AWARD_PERIOD, A.ACAD_CAREER, SUM(A.OFFER_AMOUNT) AS TOTAL_OFFER, B.FED_NEED, TO_CHAR(sysdate, 'yyyy/mm/dd') systemdate 
FROM PS_STDNT_AWARDS A 
LEFT OUTER JOIN  PS_STDNT_AWD_PER B ON  A.EMPLID = B.EMPLID AND A.INSTITUTION = B.INSTITUTION AND A.AID_YEAR = B.AID_YEAR AND B.AWARD_PERIOD = A.AWARD_PERIOD
WHERE (A.AID_YEAR in %bquote(('&list_of_aid_years.'))  AND A.AWARD_STATUS in ('O','A') AND A.AWARD_PERIOD in ('A','B') AND A.ACAD_CAREER = 'UGRD' )
GROUP BY  A.EMPLID,  A.INSTITUTION,  A.AID_YEAR, A.AWARD_PERIOD, A.ACAD_CAREER,  B.FED_NEED, sysdate
); quit;

/* check for errors now */
%let status_cd=&syscc.;
%PUT "******* status of the job is: &status_cd. *****";

proc sql; 
%include "&passthru."; 
create table &my_data3. as 
select * from connection to oracle 
(
SELECT DISTINCT A.EMPLID, A.ACAD_CAREER, A.STRM, CASE WHEN A.STDNT_ENRL_STATUS = 'E' THEN 1 ELSE 0 END AS ENRL_IND, TO_CHAR(sysdate, 'yyyy/mm/dd') systemdate 
FROM PS_STDNT_ENRL_VW A
WHERE (a.strm  in %bquote(('&list_of_strms.'))
AND A.ACAD_CAREER = 'UGRD'
AND A.STDNT_ENRL_STATUS = 'E')
); quit;

/* check for errors now */
%let status_cd=&syscc.;
%PUT "******* status of the job is: &status_cd. *****";

proc sql; 
%include "&passthru."; 
create table &my_data4. as 
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
) ;quit;

/* check for errors now */
%let status_cd=&syscc.;
%PUT "******* status of the job is: &status_cd. *****";

/* Do not normally use this, this was for testing the condition where a data set exists but has no obs */
/*data crse_grade_data;*/
/*set _null_;*/
/*run;*/

/* No error checking here, this just writes data to correct libname, in this case on the IR Z-drive folder */
%macro my_write_table(my_table);
	data dir.&my_table.;
	set &my_table.;
	run;
%mend my_write_table;

/* JUST A PLACE HOLDER BUT NEEDED FOR MACRO SWITCH TO WORK TO WORK 
   MEANING RUN CODE FOR A, B, C, ETC REPORTS EACH USES DIFFERENT MACRO */
data report_name;
set  sashelp.shoes (obs=1);
run;

%macro my_source(my_table,my_count);
proc sql;
create table source_table_status as
select 
	datetime() as source_date format = datetime23.
	,&my_count. as source_count
	,"&my_table." as table_processed
FROM report_name
;quit;
%mend my_source;

/* check for errors now */
%let status_cd=&syscc.;
%PUT "******* status of the job is: &status_cd. *****";

/* This macro checks 4 tables all exist at the same time in work temp space*/
/* If they all exist, then check if greater than zero obs in each, */
/* Then write out to libname if true */
/* Else email in the two status issues */
/* So this macro checks if all the data needed is availible and if so updates as required else has spots to send emails */
%macro check_table2(table_name1,table_name2,table_name3,table_name4);
	%global cnt1 cnt2 cnt3 cnt4;
	%let cnt1=-1; %let cnt2=-1; %let cnt3=-1; %let cnt4=-1;
  /* Test if tables exist */
  %if %sysfunc(exist(work.&table_name1.)) and %sysfunc(exist(work.&table_name2.)) and %sysfunc(exist(work.&table_name3.)) and %sysfunc(exist(work.&table_name4.)) 
  %then %do;
	%put "all tables exist";

/*	Now check if empty or not */
	proc sql noprint; 
		select count(*) into :cnt1 from work.&table_name1.;
	quit;
	proc sql noprint;
		select count(*) into :cnt2 from work.&table_name2.;
	quit;
	proc sql noprint;
		select count(*) into :cnt3 from work.&table_name3.;
	quit;
	proc sql noprint;
		select count(*) into :cnt4 from work.&table_name4.;
	quit;

/*	These are the obs counts per file just checked */
	%put &cnt1. &cnt2. &cnt3. &cnt4.;

	/* Now test if table each have at least 1 obs */
	%if &cnt1. > 0 and &cnt2. > 0 and &cnt3. > 0 and &cnt4.
	%then %do;
		%put "All tables have at least 1 obs each.";
/*		Write to libname dir location with these macro calls */
		%my_write_table(&table_name1.);
		%my_write_table(&table_name2.);
		%my_write_table(&table_name3.);
		%my_write_table(&table_name4.);

/*		Now calculate & write to the status table the action ... */
		%my_source(&table_name1.,&cnt1.);	%update_db_lookup_xd(UD_t_o_i,source_table_status,source_table_status); /* check for errors now */ %let status_cd=&syscc.; %PUT "******* status of the job is: &status_cd. *****";
		%my_source(&table_name2.,&cnt2.);	%update_db_lookup_xd(UD_t_o_i,source_table_status,source_table_status); /* check for errors now */ %let status_cd=&syscc.; %PUT "******* status of the job is: &status_cd. *****";
		%my_source(&table_name3.,&cnt3.);	%update_db_lookup_xd(UD_t_o_i,source_table_status,source_table_status); /* check for errors now */ %let status_cd=&syscc.; %PUT "******* status of the job is: &status_cd. *****";
		%my_source(&table_name4.,&cnt4.);	%update_db_lookup_xd(UD_t_o_i,source_table_status,source_table_status); /* check for errors now */ %let status_cd=&syscc.; %PUT "******* status of the job is: &status_cd. *****";
/*		Turned off as requested by Jon*/
/*		%send_mail_g;*/
	%end;
	%else %do;
		%put "At least one table have at 0 obs. All tables should have data.";
		/* Add email logic here */
		/* show error status */
   		%put &syscc.;
		%put &pgmname.;
		%send_mail_b2;
	%end;
  %end;
  %else %do;
		%Put "At least one table does not exist. All four tables should be in memory. (work -libname)";
		/* Add email logic here */
		/* show error status */
		%put &syscc.;
		%put &pgmname.;
		%send_mail_b1;
  %end;
%mend check_table2;
/* good / process */
%check_table2(&my_data4.,&my_data3.,&my_data2.,&my_data1.);

/* To test for email logic above, 'bad check' (as in force a failure to watch code through process and see if it sends correct email er-ror message etc.), 
   note: the name of the last file in the four tables passed name: bad_file_here_does_not_exist,
   that should not exist unless there were edits made above to code */
/*%check_table2(&my_data4.,&my_data3.,&my_data2., bad_file_here_does_not_exist);*/
