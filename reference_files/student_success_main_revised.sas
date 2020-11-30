* --------------------------------------------------------------------------------------------------;
*                                                                                                   ;
*  Student success                                                                                 ;
*                                                                                                   ;
* --------------------------------------------------------------------------------------------------;

title1 ; title2 ; title3 ; title4 ; title5 ; title6 ; title7 ; title8 ; title9 ; title10 ; 
footnote1 ; footnote2 ; footnote3 ; footnote4 ; footnote5 ; footnote6 ; footnote7 ;  footnote8 ;footnote9 ; footnote10 ;
options mlogic mprint merror symbolgen ;

libname rwallace odbc dsn=rwallace schema = dbo;
libname census odbc dsn=census schema = dbo;
libname cenraw odbc dsn=cenraw schema = dbo;


%Let FName = %SysGet( SAS_EXECFILEPATH ) ;
%put &fname;
%let sasfile= %sysget(SAS_EXECFILEname);
%put &sasfile ;
%let odsfile=%qsubstr(&sasfile,1, %length(&sasfile)-4);
%put &odsfile;
%Let PName = %qsubstr(%sysget(SAS_EXECFILEPATH),1, %length(%sysget(SAS_EXECFILEPATH))-%length(%sysget(SAS_EXECFILEname))) ;
%put &pname;

%macro fdate(fmt);
   %global fdate;
   %global tdate;
   data _null_;
      call symput("fdate",left(put("&sysdate9"d,&fmt)));
      call symput("tdate",left(put(today(),&fmt)));
   run;
%mend fdate;
%fdate(date9.) ;
%put &fdate ;
%put &tdate ;

%let outputfile=&odsfile. Summary Data &tdate..xls; 
%put &outputfile;


%let start_term_code=20032;
%let start_strm='2125';
%let campus='VANCO';
%let list_admit_type=('FRS' 'IFR' 'IPF' 'TRN' 'IPT' 'ITR');
  
PROC IMPORT OUT= WORK.School_code
            DATAFILE= "Z:\Student\Retention and Graduation\Student Retention & Graduation Predictive Models\school_code_xw.csv" 
            DBMS=CSV REPLACE;
     GETNAMES=YES;
     DATAROW=2; 
RUN;
    
PROC IMPORT OUT= WORK.School_lunch 
            DATAFILE= "Z:\Student\Retention and Graduation\Student Retention & Graduation Predictive Models\Free_Reduced_Price_Lunch_WA.csv" 
            DBMS=CSV REPLACE;
     GETNAMES=YES;
     DATAROW=2; 
RUN; 

PROC IMPORT OUT= WORK.teacher_education 
            DATAFILE= "Z:\Student\Retention and Graduation\Student Retention & Graduation Predictive Models\teacher_education.csv" 
            DBMS=CSV REPLACE;
     GETNAMES=YES;
     DATAROW=2; 
RUN;

  
PROC IMPORT OUT= WORK.IS_Cohort_2015 
            DATAFILE= "Z:\Grant Request for Data\Invest in Success\Invest_Sucesss_2015_cohort.xlsx" 
            DBMS=EXCEL REPLACE;
     RANGE="Sheet1$"; 
     GETNAMES=YES;
     MIXED=NO;
     SCANTEXT=YES;
     USEDATE=YES;
     SCANTIME=YES;
RUN;
 


*345044;
* --- get all students 10th day records from rWallace---;
proc sql;
create table student_wall as
select 
	term_code,
	substr(put(term_code,5.),1,1) || substr(put(term_code,5.),3,2) || put(mod(term_code,10)*2+1,1.) as strm,
	wsu_id,
	put(wsu_id,Z9.) as emplid length=11,
	ipeds_class_code,
	ftpt_code as ipeds_full_part_time,
	class_standing_code,
    degree_program_1_level_code,
	honors_program_ind,
    case when class_standing_code = 1 then '10'
		 when class_standing_code = 2 then '20'
		 when class_standing_code = 3 then '30'
		 when class_standing_code = 4 then '40'
		 when class_standing_code = 5 then '50'
		 when class_standing_code = 8 then '08'
		 							  else ' '
									  end as acad_level_bot length=3,
	case when ftpt_code='F' then 1
							else 0
							end as ipeds_full_time_ind,
	gender as sex,
	ethnic_origin_enhanced_code,
	ethnic_origin_enhanced,
	cum_gpa,
	transfer_gpa,
	cum_total_credit_hours as cum_credit_hours,
	Type,
	campus_new,
	zzusis_campus
from rwallace.student_10th_day 
where
	term_code >= &start_term_code.
	and mod(term_code,10)in (1,3)
	and enrollment_status_code = 3
	and total_credits > 0
	and ipeds_class_code = 'U'
	and class_standing_code in (1,2,3,4)
order by wsu_id
;
quit;



** Getting transfer end of term data;
*345044;
proc sql;
 create table student_wall1 as 
 select 
 a.*,
 b.non_wsu_transfer_hours as transfer_hours_eot
 from student_wall as a
left join rwallace.student_eot as b
on a.wsu_id = b.wsu_id
and a.term_code = b.term_code
;
quit;


*317703;
* --- get all student enrolled in census ---;
proc sql;
create table student_cen as
select
	term_code,
	wsu_id,
	strm,
	aid_year,
	emplid,
	ipeds_class_code,
	ipeds_full_part_time,
	acad_level_bot,
	sex,
	ipeds_legacy_ethnic_group 		as ethnic_origin_enhanced_code,
	ipeds_ethnic_group_descr 	as ethnic_origin_enhanced,
	cum_transfer_hours as transfer_hours,
	adj_admit_type,
	pell_eligibility_ind,
	ipeds_minority_ind,
	first_gen_flag,
	WA_residency,
	withdraw_code,
	withdraw_reason,
	cum_gpa,
	cum_credit_hours,
	adj_acad_prog_primary_campus 
from census.student_enrolled_vw
where snapshot='census'
	and strm >= &start_strm.
	and substr(strm,4,1)in ('3','7')
	and ipeds_class_code = 'U'
	and ipeds_ind = 1
	and term_credit_hours > 0
	and acad_level_bot  in ('10','20','30','40')
 order by emplid, strm	
;
quit;


** Getting transfer end of term data;
*289535;
proc sql;
 create table census_eot as 
 select 
 emplid,
 strm,
 cum_adj_transfer_hours as transfer_hours_eot
 from census.student_enrolled_vw 
where snapshot = 'eot'
	and strm >= &start_strm.
	and substr(strm,4,1)in ('3','7')
	and ipeds_class_code = 'U'
	and ipeds_ind = 1
	and term_credit_hours > 0
	and acad_level_bot  in ('10','20','30','40')
order by emplid, strm
;
quit;


** Putting eot data back to main census file;
*317703;
data student_cen1;
 Merge student_cen census_eot;
by emplid strm;
if term_code = . then delete;
proc sort nodupkey;
 by emplid strm;
run;


*Setting Wallace and Census files together;
*662747;
Data student_set;
 set student_wall1 student_cen1;
proc sort;
 by emplid term_code;
run;


** Getting pharmacy and vet student id numbers to pull them out of the sample;
** First from Wallace;
*2318;
proc sql;
create table student_vetpharm as
select distinct
	wsu_id,
	put(wsu_id,Z9.) as emplid length=11,
	postbacc_type,
	postbacc_type_code
from rwallace.student_10th_day 
where
	term_code >= &start_term_code.
	and term_code < 20123
	and enrollment_status_code = 3
	and total_credits > 0
	and postbacc_type_code in ('D','P')
order by wsu_id
;
quit;


** Now from Census;
*1537;
proc sql;
create table student_cen_vetpharm as
select distinct
	wsu_id,
	put(wsu_id,Z9.) as emplid length=11,
	acad_career	
from census.student_enrolled_vw 
where snapshot='census'
	and strm >= &start_strm.
	and ipeds_ind = 1
	and term_credit_hours > 0
	and acad_career in ('VETM','PHAR')
order by wsu_id
;
quit;

Data vetpharm;
 set student_vetpharm;
proc sort ;
 by wsu_id;
run;

Data cenvetpharm;
 set student_cen_vetpharm;
proc sort;
 by wsu_id;
run;

*3459;
Data allvetpharm;
 set vetpharm cenvetpharm;
proc sort  nodupkey;
 by emplid;
run;

*521736--has vet and pharm students who were not undergrads here but I will take those out later;
Data Student;
 MErge student_set allvetpharm;
by wsu_id;
if term_code = . then delete;
proc freq;
 tables term_code;
run;

*58359;
*15180 Vancouver TRN/FRS spring 2019;
*getting test scores for all students from Corinna's Freshman file;
*This matches reported Pullman entering cohort size;
proc sql;
 create table student_freshtest as 
 select distinct
   a.emplid,
   input(a.emplid,12.) as wsu_id,
   a.term_code,
   a.strm,
   a.admit_term,
   b.aid_year,
   input(b.aid_year,12.) as aidyear,
   a.adj_admit_type,
   a.adj_admit_campus,
   a.sex,
   a.wa_residency,
   a.ipeds_minority_ind,
   a.ipeds_ethnic_group,
   a.ipeds_ethnic_group_descr,
   a.pell_eligibility_ind,
   a.geog_origin_area_code,
   a.geog_origin_area_descr50,
   a.first_gen_flag,
   a.last_sch_attend,
   a.high_school_gpa,
   a.transfer_gpa,
   a.transfer_hours,
   a.qvalue,
   a.best,
   a.sat_i_comp,
   a.sat_i_math,
   a.sat_i_verb,
   a.sat_i_wr,
   a.act_comp,
   a.act_math,
   a.act_read,
   a.act_wr,
   a.age,
   a.eot_term_gpa,
   a.eot_term_gpa_hours,
   a.eot_withdraw_code,
   a.eot_withdraw_reason_descr,
   a.eot_withdraw_ind,
   a.eot_deficient_ind,
   a.sat_erws,
   a.sat_mss,
   a.bestr,
   a.avalue,
   a.acad_level_bot,
   a.ipeds_full_time_ind,
   a.eot_term_credit_hours_earned,
   a.eot_term_grade_points,
   a.eot_cum_gpa,
   a.eot_cum_credit_hours_earned,
   a.eot_cum_adj_transfer_hours,
   a.eot_cum_credit_hours
from census.NEW_student_profile_ugrd_cs a
left join census.xw_term b
 on a.term_code = b.term_code 
 and b.acad_career ne 'IALC'
where a.term_code >= &start_term_code.
 and a.adj_admit_type in &list_admit_type.
 and a.adj_admit_campus = &campus.
order by a.emplid
 ;
 quit;

 *45757;
data temp;
  set student_freshtest;
if first_gen_flag = '' then first_gen_flag = 'N';
proc freq;
 tables pell_eligibility_ind*term_code first_gen_flag*term_code;
run;

** Getting financial aid data from Wallace;
 * Year_tot is really term total;
*1776867;
proc sql;
 create table wall_finaid as 
 select 
 a.wsu_id,
 put(a.wsu_id,Z9.) as emplid length=11,
 a.finaid_fy as aidyear,
 put(a.finaid_fy,Z4.) as aid_year length=4,
 a.ap,
 a.fafreceiptdate,
 a.need as fed_need,
 b.ay,
 b.term_code,
 case when b.aidfundcode in ('AAW11','AAW12','AAW21','AAW22','AAW31','AAW32','UAAR1','UA082','UA091') then awarded_amt else 0 end as UAA1,
 case when b.aidfundcode in ('CAF01','CAF02','CAF03','CAF04','CAFF1','CAFF2','CAFF3','CAFF4','CAA$1','CA091','CA101') then awarded_amt else 0 end as CAA1,
 case when b.aidfundcode in ('R$F01','R$N01','R$S01','RT$01','RTF01','RTF02','RTF03','RTF04','RTN01','RTS01') then awarded_amt else 0 end as Regents1, 
 case when b.aidfundcode in ('SNGLH','TU201','UU213','UU200','UU201','UU500','UU501') then awarded_amt else 0 end as State_Need1,
 case when b.aidfundcode in ('L5300','L5310','L5320') then awarded_amt else 0 end as Perkins1,
 b.aidfundcode,
 b.statuscode,
 b.awarded_amt,
 b.delivered_amt,
 case when c.typecode = 'L' then b.delivered_amt else b.awarded_amt end as accepted_amt,
 c.typecode,
 c.aidprogramtype
 from rwallace.finaid_demographics as a
 left join rwallace.finaid_award as b
  on a.wsu_id = b.wsu_id 
  and a.finaid_fy = b.finaid_fy
 left join rwallace.finaid_fund c
  on b.aidfundcode = c.aidfundcode
  and b.finaid_fy = c.finaid_fy
 where b.statuscode = 'A'
  and b.ay >= 2004
  group by a.wsu_id, b.ay
  order by a.wsu_id, b.ay
 ;
 quit;

 data temp;
  set wall_finaid;
 if wsu_id ne 661050 then delete;
 if aid_year ne '2008' then delete;
 run;

 *151468;
proc sql;
 create table wall_finaid1 as
 select distinct
 wsu_id,
 emplid,
 aidyear,
 aid_year,
 ap,
 fafreceiptdate,
 fed_need ,
 ay,
 sum(UAA1) as UAA,
 sum(CAA1) as CAA ,
 sum(State_Need1) as State_need ,
 sum(Perkins1) as Perkins,
 sum(awarded_amt) as total_offer,
 sum(accepted_amt) as total_accept,
 sum(delivered_amt) as total_disb
 from wall_finaid a
 group by emplid, aid_year
 ;
 quit;

  data temp;
  set wall_finaid1;
 if wsu_id ne 661050 then delete;
 if aid_year ne '2008' then delete;
 run;


 *151468;
data wall_finaid2;
 set wall_finaid1;
FAFSADate = FAFReceiptDate;
format FAFSAdate mmddyy10.;
informat FAFSAdate mmddyy10.;
run;


** Getting financial aid data from Census for 2012 and any year that is not most recent year;  
** Please note in this model originally I did not restrict award period.;
** If I need to match net price or concerned about EFC then need to use A,B; 
*347667 (A,B);
proc sql;
 create table cen_finaid1a as 
 select distinct
 a.emplid,
 input(a.aid_year,11.) as aidyear,
 a.snapshot,
 a.aid_year,
 case when a.efc_status = 'O' then a.fed_need 
      when a.efc_status = 'U' then . end as fed_need1,
 case when a.efc_status = 'O' then a.fed_unmet_need 
      when a.efc_status = 'U' then . end as fed_unmet_need1,
 case when a.efc_status = 'O' then a.fed_need_base_aid
	  when a.efc_status = 'U' then . end as fed_need_base_aid1,
 case when a.efc_status = 'O' then  a.fed_year_coa
	  when a.efc_status = 'U' then . end as fed_year_coa1,
 case when a.efc_status = 'O' then  a.fed_efc 
      when a.efc_status = 'U' then . end as fed_efc1,
 case when a.efc_status = 'O' then  a.prorated_efc
 	  when a.efc_status = 'U' then . end as prorated_efc1,
/* a.fin_aid_type_descr_xw,*/
/* a.loan_interest_attr_descr,*/
 b.application_received_dt
from census.fa_award_period as a
inner join (select distinct aid_year, min(snapshot)as snapshot from census.fa_isir 
                              group by aid_year) csnap
      on a.aid_year=csnap.aid_year
      and a.snapshot=csnap.snapshot 
left join census.fa_isir b
 on csnap.snapshot= b.snapshot
/* on a.snapshot = b.snapshot*/
 and a.emplid = b.emplid
 and a.aid_year = b.aid_year
where a.fed_need is not null
 and a.award_period in ('A','B')
/* and a.aid_year < '2019' and a.snapshot = 'aidyear'*/
 group by a.emplid, a.aid_year
 order by a.emplid, a.aid_year
 ; quit;

 
data temp;
  set cen_finaid1a;
 if emplid ne '011556066' then delete;
run;
 


 *794584 - A,B aid year vw;
proc sql;
 create table cen_finaid1b as 
 select 
 a.*,
 case when b.item_type in ('900505011550','900505011560','900505011570','900505011600','900505011610','900505011620','900505011630',
                              '900505011635','900505011640','900505011645','900505011646','900505011647','900505011648','900505011649',
                              '900505011650','900505011651','900505011652','900505011653','900505011654','900505011655','900505011656',
                              '900505043209','900505043210','900505043211','900505043212',
                              '900505012510','900505012515', /* These two are international */
							  '900505001845','900505001846','900505032662','900505032663','900505001847',/* These are tri-cities */
							  '900505043140','900505043144','900505001805','900505001806','900505001807','900505001808' /* These are Vancouver*/
																			)		then accept_amt else 0 end as CAA,
 case when b.item_type in ('900505011000','900505011010','900505011020','900505011030','900505011031','900505011032','900505011033',
							  '900505011034','900505011040','900505011050','900505011060','900505011070','900505011658','900505011659',
							  '900505011660','900505011661','900505011662','900505011663','900505011664','900505011665',
							  '900105005013',  /*Note the last item type is not a waiver but was used in place of a waiver */	
							  '900505001853','900505032644','900505001854','900505032645','900505001855','900505032646','900505001856','900505001857',
							  '900505032648','900505001858','900505032649','900505001859','900505032650','900505001860','900505001861','900505032652',
							  '900505001862','900505032653','900505001863','900505032654',,'900505001864', /* These are TriCities */	
							  '900505001809','900505001810','900505001811','900505001812'                  /* These are Vancouver */ 	
																			)		then accept_amt else 0 end as UAA,
 case when b.item_type in ('900103003000','900103003005','900103003010','900103003015','900103003020','900103003011') then accept_amt else 0 end as Stateneed,
 case when b.item_type in ('901501005000','901501005010','901501005020','901501005100') then accept_amt else 0 end as Perkins,
 case when b.federal_id ne 'PLUS' 													then accept_amt else 0 end as allbutplus,

 case when b.fin_aid_type = 'G' 										 			then accept_amt else 0 end as grant, 
 case when b.fin_aid_type in ('S','A') 												then accept_amt else 0 end as scholarship,   /* sk edited here */

 case when b.fin_aid_type in ('V') and b.item_type =   '900505004051'						then accept_amt else 0 end as wvr_need,    /* SK edited here */
 case when b.fin_aid_type in ('V') and b.item_type <>  '900505004051'						then accept_amt else 0 end as wvr_merit,   /* SK edited here */

 case when b.fin_aid_type = 'L' and b.loan_interest_attr = 'S' and b.federal_id ne 'PLUS'	then disbursed_amt else 0 end as loan_sub,
 case when b.fin_aid_type = 'L' and b.loan_interest_attr = 'U' and b.federal_id ne 'PLUS' 	then disbursed_amt else 0 end as loan_unsub, 
 case when b.fin_aid_type = 'L' and b.federal_id = 'PLUS' 									then disbursed_amt else 0 end as loan_plus, 

 case when b.fin_aid_type = 'W' 								then accept_amt else 0 end as work_study,

 
 case when b.item_type in ('900505004000','900505004010','900505004020','900505004030','900505004040','900505004050','900505004051', 
                           '900105005055','900105005056'  /* These last two are hard funded */
																			)		then accept_amt else 0 end as Cougar_Comm_acp,
 case when b.item_type in ('900305036060','900305036061','900505001753','900505001754','900505001755','900505001756','900505032724',
							  '900505032725','900505032726','900505032727','900505001757','900505001758','900505001759','900505001760',
							  '900505001813','900505001814','900505001815','900505032760','900505032761','900505032762','900505032763',
							  '900505001836','900505001837','900505001838','900505043205','900505043206','900505043207','900505043208',
							  '900105005012',/* note the last is not a waiver but a substition to hard dollars */
                              '900505001784', /* This one is everett*/
							  '900505001865','900505032656','900505001866','900505032657','900505001867','900505032658','900505001868','900505032659',
							  '900505001869','900505032660','900505001870','900505032661',  /* These are Tri-Citeis */
							  '900505001813','900505001814','900505001837','900505001815','900505001838'  /* These are Vancouver */
							  												)		then accept_amt else 0 end as crimson_transfer_acp,
  case when b.item_type in ('900505043205',
                            '900505001781','900505001782'  /* These two are Everett */ 
                            '900505012500','900505012505'  /* These two are international */
							'900505001849','900505032666','900505001850','900505032668',  /* These are tri-cities */
						    												)		then accept_amt else 0 end as crimson_transfer_wue_acp,	

 b.disbursed_amt,
 b.offer_amt,
 b.accept_amt
 from cen_finaid1a as a
/* inner join (select distinct aid_year, min(snapshot)as snapshot from census.fa_isir */
/*                              group by aid_year) csnap*/
/*      on a.aid_year=csnap.aid_year*/
/*      and a.snapshot=csnap.snapshot */
 left join census.fa_award_aid_year_vw as b
/*  on csnap.snapshot= b.snapshot*/
  on a.snapshot = b.snapshot
  and a.emplid = b.emplid
  and a.aid_year = b.aid_year
  and b.award_period in ('A','B')
  and b.award_status = 'A'  
  group by a.emplid, a.aid_year
 order by a.emplid, a.aid_year
 ;
 quit;


data temp;
  set cen_finaid1b;
 if emplid ne '011556066' then delete;
run;



*347667;
proc sql;									
create table cen_finaid as
select distinct
 emplid,
 aidyear,
 aid_year,
 application_received_dt,
 fed_need1 as fed_need,
 fed_unmet_need1 as fed_unmet_need,
 fed_need_base_aid1 as fed_need_base_aid,
 fed_year_coa1 as fed_year_coa,
 fed_efc1 as fed_efc,
 prorated_efc1 as prorated_efc,
 sum (caa) as caa,
 sum (uaa) as uaa,
 sum (stateneed) as state_need,
 sum (Perkins) as Perkins,
 sum (allbutplus) as all_aid_x_plus,
 sum (grant) as grant_tot,
 sum (scholarship) as schol_tot,
 sum (wvr_need) as need_waiver_tot,
 sum (wvr_merit) as merit_waiver_tot,
 sum (loan_sub) as sub_loan_tot,
 sum (loan_unsub) as unsub_loan_tot,
 sum (loan_plus) as plus_loan_tot,
 sum (work_study) as work_study_tot,
 sum (cougar_comm_acp) as cougar_comm_tot,
 sum (crimson_transfer_acp) as crim_tran_tot,
 sum (crimson_transfer_wue_acp) as crim_tran_nr_tot,
 sum (disbursed_amt) as total_disb,
 sum (offer_amt) as total_offer,
 sum (accept_amt) as total_accept
from cen_finaid1b
group by emplid, aid_year
order by emplid
;
quit;

data temp;
  set cen_finaid;
 if emplid ne '011556066' then delete;
run;


*347667;
data cen_finaid_all;
 set cen_finaid ;
FAFSADate = datepart(application_received_dt);
format FAFSADate mmddyy10.;
informat FAFSADate mmddyy10.;
proc sort;
 by emplid aid_year;
run;

data temp;
  set cen_finaid_all;
 if emplid ne '011556066' then delete;
run;


* stack all finaid;
*499145;
data finaid_all;
 set wall_finaid2 cen_finaid_all;
drop application_received_dt FAFReceiptDate;
proc sort;
 by emplid aid_year;
run;



  data temp;
  set finaid_all;
 if wsu_id ne 661050 then delete;
 if aid_year ne '2008' then delete;
 run;


*15180;
proc sql;
 create table student_finaid as
 select distinct
 a.*,
 b.fafsadate as fafsadate_yr1,
 b.fed_need as fed_need_yr1,
 b.fed_unmet_need as fed_unmet_need_yr1,
 b.fed_need_base_aid as fed_need_base_aid_yr1,
 b.fed_year_coa as fed_year_coa_yr1,
 b.fed_efc as fed_efc_yr1,
 b.prorated_efc as prorated_efc_yr1,
 b.caa as caa_yr1,
 b.uaa as uaa_yr1,
 b.state_need as state_need_yr1,
 b.perkins as perkins_yr1,
 b.all_aid_x_plus as all_aid_x_plus_yr1,
 b.grant_tot as grant_tot_yr1,
 b.schol_tot as schol_tot_yr1,
 b.need_waiver_tot as need_waiver_tot_yr1,
 b.sub_loan_tot as sub_loan_tot_yr1,
 b.unsub_loan_tot as unsub_loan_tot_yr1,
 b.plus_loan_tot as plus_loan_tot_yr1,
 b.work_study_tot as work_study_tot_yr1,
 b.cougar_comm_tot as cougar_comm_tot_yr1,
 b.crim_tran_tot as crim_tran_tot_yr1,
 b.crim_tran_nr_tot as crim_tran_nr_yr1,
 b.total_disb as total_disb_yr1,
 b.total_offer as total_offer_yr1,
 b.total_accept as total_accept_yr1,

 c.fafsadate as fafsadate_yr2,
 c.fed_need as fed_need_yr2,
 c.fed_unmet_need as fed_unmet_need_yr2,
 c.fed_need_base_aid as fed_need_base_aid_yr2,
 c.fed_year_coa as fed_year_coa_yr2,
 c.fed_efc as fed_efc_yr2,
 c.prorated_efc as prorated_efc_yr2,
 c.caa as caa_yr2,
 c.uaa as uaa_yr2,
 c.state_need as state_need_yr2,
 c.perkins as perkins_yr2,
 c.all_aid_x_plus as all_aid_x_plus_yr2,
 c.grant_tot as grant_tot_yr2,
 c.schol_tot as schol_tot_yr2,
 c.need_waiver_tot as need_waiver_tot_yr2,
 c.sub_loan_tot as sub_loan_tot_yr2,
 c.unsub_loan_tot as unsub_loan_tot_yr2,
 c.plus_loan_tot as plus_loan_tot_yr2,
 c.work_study_tot as work_study_tot_yr2,
 c.cougar_comm_tot as cougar_comm_tot_yr2,
 c.crim_tran_tot as crim_tran_tot_yr2,
 c.crim_tran_nr_tot as crim_tran_nr_yr2,
 c.total_disb as total_disb_yr2,
 c.total_offer as total_offer_yr2,
 c.total_accept as total_accept_yr2,

 d.fafsadate as fafsadate_yr3,
 d.fed_need as fed_need_yr3,
 d.fed_unmet_need as fed_unmet_need_yr3,
 d.fed_need_base_aid as fed_need_base_aid_yr3,
 d.fed_year_coa as fed_year_coa_yr3,
 d.fed_efc as fed_efc_yr3,
 d.prorated_efc as prorated_efc_yr3,
 d.caa as caa_yr3,
 d.uaa as uaa_yr3,
 d.state_need as state_need_yr3,
 d.perkins as perkins_yr3,
 d.all_aid_x_plus as all_aid_x_plus_yr3,
 d.grant_tot as grant_tot_yr3,
 d.schol_tot as schol_tot_yr3,
 d.need_waiver_tot as need_waiver_tot_yr3,
 d.sub_loan_tot as sub_loan_tot_yr3,
 d.unsub_loan_tot as unsub_loan_tot_yr3,
 d.plus_loan_tot as plus_loan_tot_yr3,
 d.work_study_tot as work_study_tot_yr3,
 d.cougar_comm_tot as cougar_comm_tot_yr3,
 d.crim_tran_tot as crim_tran_tot_yr3,
 d.crim_tran_nr_tot as crim_tran_nr_yr3,
 d.total_disb as total_disb_yr3,
 d.total_offer as total_offer_yr3,
 d.total_accept as total_accept_yr3,

 e.fafsadate as fafsadate_yr4,
 e.fed_need as fed_need_yr4,
 e.fed_unmet_need as fed_unmet_need_yr4,
 e.fed_need_base_aid as fed_need_base_aid_yr4,
 e.fed_year_coa as fed_year_coa_yr4,
 e.fed_efc as fed_efc_yr4,
 e.prorated_efc as prorated_efc_yr4,
 e.caa as caa_yr4,
 e.uaa as uaa_yr4,
 e.state_need as state_need_yr4,
 e.perkins as perkins_yr4,
 e.all_aid_x_plus as all_aid_x_plus_yr4,
 e.grant_tot as grant_tot_yr4,
 e.schol_tot as schol_tot_yr4,
 e.need_waiver_tot as need_waiver_tot_yr4,
 e.sub_loan_tot as sub_loan_tot_yr4,
 e.unsub_loan_tot as unsub_loan_tot_yr4,
 e.plus_loan_tot as plus_loan_tot_yr4,
 e.work_study_tot as work_study_tot_yr4,
 e.cougar_comm_tot as cougar_comm_tot_yr4,
 e.crim_tran_tot as crim_tran_tot_yr4,
 e.crim_tran_nr_tot as crim_tran_nr_yr4,
 e.total_disb as total_disb_yr4,
 e.total_offer as total_offer_yr4,
 e.total_accept as total_accept_yr4,

 f.fafsadate as fafsadate_yr5,
 f.fed_need as fed_need_yr5,
 f.fed_unmet_need as fed_unmet_need_yr5,
 f.fed_need_base_aid as fed_need_base_aid_yr5,
 f.fed_year_coa as fed_year_coa_yr5,
 f.fed_efc as fed_efc_yr5,
 f.prorated_efc as prorated_efc_yr5,
 f.caa as caa_yr5,
 f.uaa as uaa_yr5,
 f.state_need as state_need_yr5,
 f.perkins as perkins_yr5,
 f.all_aid_x_plus as all_aid_x_plus_yr5,
 f.grant_tot as grant_tot_yr5,
 f.schol_tot as schol_tot_yr5,
 f.need_waiver_tot as need_waiver_tot_yr5,
 f.sub_loan_tot as sub_loan_tot_yr5,
 f.unsub_loan_tot as unsub_loan_tot_yr5,
 f.plus_loan_tot as plus_loan_tot_yr5,
 f.work_study_tot as work_study_tot_yr5,
 f.cougar_comm_tot as cougar_comm_tot_yr5,
 f.crim_tran_tot as crim_tran_tot_yr5,
 f.crim_tran_nr_tot as crim_tran_nr_yr5,
 f.total_disb as total_disb_yr5,
 f.total_offer as total_offer_yr5,
 f.total_accept as total_accept_yr5,

 g.fafsadate as fafsadate_yr6,
 g.fed_need as fed_need_yr6,
 g.fed_unmet_need as fed_unmet_need_yr6,
 g.fed_need_base_aid as fed_need_base_aid_yr6,
 g.fed_year_coa as fed_year_coa_yr6,
 g.fed_efc as fed_efc_yr6,
 g.prorated_efc as prorated_efc_yr6,
 g.caa as caa_yr6,
 g.uaa as uaa_yr6,
 g.state_need as state_need_yr6,
 g.perkins as perkins_yr6,
 g.all_aid_x_plus as all_aid_x_plus_yr6,
 g.grant_tot as grant_tot_yr6,
 g.schol_tot as schol_tot_yr6,
 g.need_waiver_tot as need_waiver_tot_yr6,
 g.sub_loan_tot as sub_loan_tot_yr6,
 g.unsub_loan_tot as unsub_loan_tot_yr6,
 g.plus_loan_tot as plus_loan_tot_yr6,
 g.work_study_tot as work_study_tot_yr6,
 g.cougar_comm_tot as cougar_comm_tot_yr6,
 g.crim_tran_tot as crim_tran_tot_yr6,
 g.crim_tran_nr_tot as crim_tran_nr_yr6,
 g.total_disb as total_disb_yr6,
 g.total_offer as total_offer_yr6,
 g.total_accept as total_accept_yr6

from student_freshtest a
left join finaid_all b
 on a.emplid = b.emplid
 and a.aidyear =  b.aidyear  
left join finaid_all c
 on a.emplid = c.emplid
 and c.aidyear = a.aidyear + 1
left join finaid_all d
 on a.emplid = d.emplid
 and d.aidyear = a.aidyear + 2
left join finaid_all e
 on a.emplid = e.emplid
 and e.aidyear = a.aidyear + 3 
left join finaid_all f
 on a.emplid = f.emplid
 and f.aidyear = a.aidyear + 4
left join finaid_all g
 on a.emplid = g.emplid
 and g.aidyear = a.aidyear + 5
order by a.emplid, a.term_code
;
quit;


  data temp;
  set student_finaid;
 if wsu_id ne 661050 then delete;
 if aid_year ne '2008' then delete;
 run;




* but I need to have whether or not they eventually enrolled in vet or pharm;
* This matches pullman freshmen cohort reported numbers;
*49817;
Data New_fresh;
 merge student_finaid allvetpharm;
by emplid;
*if acad_career = 'VETM' then delete;
*if acad_career = 'PHAR' then delete;
*if postbacc_type_code = 'D' then delete;
*if postbacc_type_code = 'P' then delete;
*If adj_admit_type ne 'FRS' then delete;
if term_code = . then delete;
proc sort nodupkey;
 by emplid;
proc sort;
 by admit_term1;
proc freq;
 tables term_code*first_gen_flag;
run;

* --- get all degree awarded records in legacy system ---;
*45208;
proc sql;
create table legdegree as
select
	wsu_id,
	degree_term_code,
	substr(put(degree_term_code,5.),1,1) || substr(put(degree_term_code,5.),3,2) || put(mod(degree_term_code,10)*2+1,1.) as completion_term,
	cumulative_gpa as degree_gpa,
	cumulative_total_credit_hours as degree_ch
from rwallace.sdw_degrees
where degree_term_code >= &start_term_code.
	and degree_conferment_status_code='DC'
	and degree_category_level_code = 'B'
group by wsu_id
;
quit;

* --- get all degree awarded records in census ---;
*34531;
proc sql;
create table cendegree as
select 
  wsu_id,
  completion_term,
  floor((input(completion_term,8.)+ 18000)/10)*10 + (input(substr(completion_term,4,1),1.)-1)/2 as degree_term_code,
  cum_gpa as degree_gpa,
  cum_adj_transfer_hours as degree_transferch,
  cum_credit_hours as degree_ch
from census.student_degree_vw  
where 
    completion_term >= '2063'
	and ipeds_ind = 1
	and acad_degr_status = 'A'
	and degree <> 'GMIN0005'
	and ((substr(education_lvl,1,1) = 'B' and acad_career = 'UGRD')
		  or education_lvl in ('DP','DM'))
;
quit;

*75823;
data degree;
set legdegree cendegree	;
proc sort; 
 by wsu_id;
proc sort nodupkey;
 by wsu_id;
run;

**************************************************** Separating out Freshmen (no Transfer admits) ********************************* ;
** Getting rid of those admitted prior to 2004, FSR, and non-degree seeking undergraduates;
*662747;
Data student_fresh;
 set student;
proc sort;
 by aid_year;
run;


Proc freq data = new_fresh;
 tables term_code;
run;

* freshmen retention status ;
* This has only students who were admitted as freshmen and did not go on to enroll in a professional program;
*49817;
proc sql;
create table Fresh_status as
select 
	s.*,
	floor(s.term_code/10) as year,
	d.degree_term_code,

	case when degree_term_code is not null and degree_term_code < s.term_code + 10 	then 1
																				    else 0
												   									end as yr1_grad,
	case when degree_term_code is not null and degree_term_code < s.term_code + 20 	then 1
																				    else 0
												   									end as yr2_grad,
	case when degree_term_code is not null and degree_term_code < s.term_code + 30 	then 1
																				    else 0
												   									end as yr3_grad,
	case when degree_term_code is not null and degree_term_code < s.term_code + 40 	then 1
																				    else 0
												   									end as yr4_grad,
	case when degree_term_code is not null and degree_term_code < s.term_code + 50 	then 1
												   									else 0
												   									end as yr5_grad,
	case when degree_term_code is not null and degree_term_code < s.term_code + 60 	then 1
												   									else 0
												   									end as yr6_grad,
	case when degree_term_code is not null and degree_term_code < s.term_code + 70 	then 1
												   									else 0
												   									end as yr7_grad,
	case when degree_term_code is not null and degree_term_code < s.term_code + 80 	then 1
												   									else 0
												   									end as yr8_grad,
	case when degree_term_code is not null and degree_term_code < s.term_code + 90 	then 1
												   									else 0
												   									end as yr9_grad,
	case when degree_term_code is not null and degree_term_code < s.term_code + 100 then 1
												   									else 0
												   									end as yr10_grad,
	case when degree_term_code is not null and degree_term_code < s.term_code + 110 then 1
												   									else 0
												   									end as yr11_grad,

	case when calculated yr1_grad = 1 							then 0
		 when calculated yr1_grad = 0 and s2.EMPLID is not null	then 1
																else 0
																end as yr2_cont,
	case when calculated yr2_grad = 1 							then 0
		 when calculated yr2_grad = 0 and s3.EMPLID is not null	then 1
																else 0
																end as yr3_cont,
	case when calculated yr3_grad = 1 							then 0
		 when calculated yr3_grad = 0 and s4.EMPLID is not null	then 1
																else 0
																end as yr4_cont,
	case when calculated yr4_grad = 1 							then 0
		 when calculated yr4_grad = 0 and s5.EMPLID is not null	then 1
																else 0
																end as yr5_cont,
	case when calculated yr5_grad = 1 							then 0
		 when calculated yr5_grad = 0 and s6.EMPLID is not null	then 1
																else 0
																end as yr6_cont,
	case when calculated yr6_grad = 1 							then 0
		 when calculated yr6_grad = 0 and s7.EMPLID is not null	then 1
																else 0
																end as yr7_cont,
	case when calculated yr7_grad = 1							then 0
		 when calculated yr7_grad = 0 and s8.EMPLID is not null	then 1
																else 0
																end as yr8_cont,
	case when calculated yr8_grad = 1							then 0
		 when calculated yr8_grad = 0 and s9.EMPLID is not null	then 1
																else 0
																end as yr9_cont,
	case when calculated yr9_grad = 1 							 then 0
		 when calculated yr9_grad = 0 and s10.EMPLID is not null then 1
																 else 0
																 end as yr10_cont,
	case when calculated yr10_grad = 1							  then 0
		 when calculated yr10_grad = 0 and s11.EMPLID is not null then 1
																  else 0
																  end as yr11_cont,
	case when calculated yr11_grad = 1							  then 0
		 when calculated yr11_grad = 0 and s12.EMPLID is not null then 1
																  else 0
																  end as yr12_cont,

	case when calculated yr1_grad = 1 or calculated yr2_cont = 1 then 0
																 else 1
																 end as yr2_not_enroll,
	case when calculated yr2_grad = 1 or calculated yr3_cont = 1 then 0
																 else 1
																 end as yr3_not_enroll,
	case when calculated yr3_grad = 1 or calculated yr4_cont = 1 then 0
																 else 1
																 end as yr4_not_enroll,
	case when calculated yr4_grad = 1 or calculated yr5_cont = 1 then 0
																 else 1
																 end as yr5_not_enroll,
	case when calculated yr5_grad = 1 or calculated yr6_cont = 1 then 0
																 else 1
																 end as yr6_not_enroll,
	case when calculated yr6_grad = 1 or calculated yr7_cont = 1 then 0
																 else 1
																 end as yr7_not_enroll,
	case when calculated yr7_grad = 1 or calculated yr8_cont = 1 then 0
																 else 1
																 end as yr8_not_enroll,
	case when calculated yr8_grad = 1 or calculated yr9_cont = 1 then 0
																 else 1
																 end as yr9_not_enroll,
	case when calculated yr9_grad = 1 or calculated yr10_cont = 1 then 0
																  else 1
																  end as yr10_not_enroll,
	case when calculated yr10_grad = 1 or calculated yr11_cont = 1 then 0
																   else 1
																   end as yr11_not_enroll,
	case when calculated yr11_grad = 1 or calculated yr12_cont = 1 then 0
																   else 1
																   end as yr12_not_enroll,

    1 as ones,
	"all" as all,
	calculated yr1_grad + calculated yr2_cont as first_year_success

from new_fresh as s

left join degree as d
	on s.wsu_id = d.wsu_id
left join student_fresh as s2
	on s.term_code + 10 = s2.term_code
	and s.emplid = s2.emplid
left join student_fresh as s3
	on s.term_code + 20 = s3.term_code
	and s.emplid = s3.emplid
left join student_fresh as s4
	on s.term_code + 30 = s4.term_code
	and s.emplid = s4.emplid
left join student_fresh as s5
	on s.term_code + 40 = s5.term_code
	and s.emplid = s5.emplid
left join student_fresh as s6
	on s.term_code + 50 = s6.term_code
	and s.emplid = s6.emplid
left join student_fresh as s7
	on s.term_code + 60 = s7.term_code
	and s.emplid = s7.emplid
left join student_fresh as s8
	on s.term_code + 70 = s8.term_code
	and s.emplid = s8.emplid
left join student_fresh as s9
	on s.term_code + 80 = s9.term_code
	and s.emplid = s9.emplid
left join student_fresh as s10
	on s.term_code + 90 = s10.term_code
	and s.emplid = s10.emplid
left join student_fresh as s11
	on s.term_code + 100 = s11.term_code
	and s.emplid = s11.emplid
left join student_fresh as s12
	on s.term_code + 110 = s12.term_code
	and s.emplid = s12.emplid

;
quit;


*Matching back final cum gpa  from degree file;
*49817;
proc sql;
 create table Fresh_status1 as
 select distinct 
 a.*,
 b.degree_gpa,
 b.degree_ch,
 b.degree_transferch
 from  Fresh_status a
 left join degree b
 on a.wsu_id = b.wsu_id
 ;
quit;

Data student_gpa;
 set student;
proc sort ;
 by emplid descending term_code ;
proc sort nodupkey;
 by emplid;
run;

Data student_gpa1;
 set student_gpa;
last_gpa = cum_gpa;
keep emplid last_gpa sex last_school_attended_code last_school_type last_school_attended 	last_school_city last_school_state ;
run;

*Matching back last available gpa to fresh file;
*49817;
data Fresh_status2;
 merge fresh_status1 student_gpa1;
by emplid;
if wsu_id  = . then delete;
check = degree_gpa - last_gpa;
if degree_gpa = . then check = 0;
final_gpa = degree_gpa;
if degree_gpa = . then final_gpa = last_gpa;
proc sort;
 by emplid;
proc freq;
 tables term_code*first_Gen_flag;
run;

** Trying to get a WSU GPA for those that don't have one;
* 387;
Data Fresh_status3;
 Set Fresh_status2;
code = 1;
If Final_gpa ne . then delete;
run;


*431;
Proc sql;
Create table last_trns as 
 select DISTINCT
 a.emplid,
 a.code,
 b.term_code as trns_term,
 b.cum_gpa as final_gpa1
 from fresh_status3 as a
 left join rwallace.h_student_transcript as b
 on a.emplid = b.emplid
 where b.term_code >= 20032
order by emplid;
;
run;

*27;
Data last_trns1;
 set last_trns;
If final_gpa1 = . then delete;
proc sort;
 by emplid descending trns_term;
proc sort nodupkey;
 by emplid;
run;


*49817;
Data Fresh_status4;
 merge Fresh_status2 last_trns1;
 by emplid;
proc sort;
 by emplid;
 proc freq;
  tables term_code*first_gen_flag;
run;


*Joining last school attending to information about the school;
*15180;
proc sql;
 create table fresh_status4a as 
 select distinct
 a.*,
 b.school_type,
 b.ext_org_descr,
 b.ext_org_city,
 b.ext_org_state,
 b.ext_org_postal,
 b.proprietorship,
 b.state_district_code,
 b.state_school_code,
 input(b.fice_cd,6.) as educ_institution_id
from fresh_status4 a
left join census.xw_school_vw b
on a.last_sch_attend = b.ext_org_id
;
quit;

*Joining in any degrees;
*need to think about whether we want to link to last school attended;
*Creating two tables, first wallace;
*15186;
proc sql;
 create table ext_degree_wallace as
 select distinct
 a.emplid,
 a.wsu_id,
 a.last_sch_attend,
 b.degree_category_code as ext_degree_code,
 b.degree_category_level_code as ext_degree_category_level_code,
 b.degree_term_code as ext_degree_term_code
 from fresh_status4a as a
left join rwallace.sdw_non_wsu_degrees as b
 on a.wsu_id = b.wsu_id 
 and a.educ_institution_id = b.educ_institution_id
order by emplid
;
quit;

*Now from Census;
*15234;
proc sql;
 create table ext_degree_census as 
 select distinct
 a.emplid,
 a.wsu_id,
 a.last_sch_attend,
 b.degree as ext_degree_code format=$16. informat=$16. length=16,
 b.degree_descr as ext_degree_descr,
 b.degree_term_code as ext_degree_term_code
 from fresh_status4a as a
 left join census.student_ext_degree_vw as b
  on a.emplid = b.emplid
  and a.last_sch_attend = b.ext_org_id
order by emplid
;
quit;

proc sql;
 create table all_schools_b as
 select 
 *
 from ext_degree_wallace 
 union
 select
 *
 from ext_degree_census 

;
quit;

*Setting the two together;
  *9721;
Data all_schools;
 set all_schools_b;
if ext_degree_term_code = . then delete;
proc sort nodupkey;
 by emplid;
run;

*15180;
proc sql;
 create table fresh_status4 as
 select distinct
 a.*,
 b.ext_degree_code,
 b.ext_degree_category_level_code,
 b.ext_degree_term_code
 from fresh_status4a a
 left join all_schools b
 on a.emplid = b.emplid
;
quit;

*we need to get new files from the state;
*49748;
proc sql;
 create table schools1 as
 select 
 *,
 put(school_id,Z4.) as state_school_code length=4
 from school_lunch
order by calculated state_school_code
; 
quit;

proc sql;
 create table schools2 as 
 select
 put(school_id,Z4.) as state_school_code length=4,
 masters
 from teacher_education
order by calculated state_school_code
;quit;

*49817;
proc sql;
 create table fresh_status5 as
 select distinct
 a.*,
 b.total_enrl,
 b.Per_Eligibile_Lunch as per_eligible_lunch,
 c.masters
 from fresh_status4 as a
 left join schools1 as b
 on a.state_school_code = b.state_school_code
 left join schools2 as c
 on a.state_school_code = c.state_school_code
 ;
 quit;

data temp;
 set fresh_status5;
proc freq;
 tables term_code*first_gen_flag;
run;


data student_set_eot;
 set student_set;
keep emplid wsu_id strm term_code transfer_hours_eot;
run;

*Merging back in eot transfer student data from set file above;
*49817;
Data Fresh_status7a;
 Merge Fresh_status5 student_set_eot;
by emplid term_code;
if adj_admit_type = '' then delete;
run;

*********************** To get adj transfer credit hours *****************************;

* cum credit hours attempted, and total_cumulative credits, transfer credits;
data student_enrolled1;
set census.new_student_enrolled;
if snapshot='census' then output;
run;

data student_enrolled1;
 set student_enrolled1;
proc sort;
 by emplid;
run;

*30059;
proc sql;
create table stdnt_car_term1 as
select
	a.strm,
	a.emplid,
	a.acad_career,
    a.tot_trnsfr + a.tot_test_credit + a.tot_other  as cum_transfer_hours
from cenraw.ps_stdnt_car_term_FY2014_degree a
inner join (select distinct strm, emplid,acad_career from student_enrolled1) c
	on a.strm = c.strm 
	and a.emplid=c.emplid
	and a.acad_career = c.acad_career
;
quit;

proc sql;
create table transfer_hours_adjustment as
select
	a.emplid,
	a.acad_career,
	sum(a.tc_units_adjust) as tot_adjustment
from cenraw.ps_stdnt_car_term_FY2014_degree a
inner join (select distinct emplid,acad_career from student_enrolled1) c
	on a.emplid=c.emplid
	and a.acad_career = c.acad_career
group by a.emplid, a.acad_career
;
quit;

proc sql;
create table stdnt_car_term_max as
select
	a.strm,
	a.emplid,
	a.acad_career,
    a.cum_transfer_hours,
	b.tot_adjustment,
      case when a.cum_transfer_hours - b.tot_adjustment < 0 then a.cum_transfer_hours
													  else a.cum_transfer_hours - b.tot_adjustment 
													  end as cum_adj_transfer_hours
from stdnt_car_term1 a
left join transfer_hours_adjustment b
	on a.emplid=b.emplid
	and a.acad_career = b.acad_career

;
quit;

*25192;
Data transfer;
 set stdnt_car_term_max;
if acad_career ne 'UGRD' then delete;
proc sort;
 by emplid strm;
run;

*****************************************************************************;
** left off here trying to figure out relationship between transfer hours;
*Merging back in adj transfer student data from transfer_credit file;
*49817;
Data fresh_status7b;
 Merge fresh_status7a transfer;
by emplid;
if wsu_id = . then delete;
transfer_credit_adj_final = cum_adj_transfer_hours;
if cum_adj_transfer_hours = . then transfer_credit_adj_final = transfer_hours_eot;
check = transfer_hours_eot - eot_cum_adj_transfer_hours;
proc sort;
 by emplid strm;
proc sort nodupkey;
 by emplid;
proc means;
 var check;
proc freq;
 tables term_code*first_gen_flag ;
run;

*************************************************************************************;
* Getting honors data;
*10139;
proc sql;
 create table honors_wall as
 select distinct 
 wsu_id,
 term_code,
 case when honors_program_ind = 'Y' then 1 else 0 end as Hon_prog_ind
 from rwallace.student_10th_day_vw 
 where honors_program_ind = 'Y'
 and term_code ge 20032
;
quit;

*5849;
proc sql;
 create table honors_cen as 
 select distinct
 wsu_id,
 term_code,
 honors_program_ind as Hon_prog_ind
 from census.student_enrolled_vw 
 where honors_program_ind = 1
 and term_code ge 20122
 ;
run;

*17656;
*Setting the two files together;
data all_honors;
 set honors_wall honors_cen;
proc sort;
 by wsu_id term_code;
run;


*49817;
data Fresh_status7c;
 Merge Fresh_status7b all_honors;
by wsu_id term_code;
if emplid = '' then delete;
if hon_prog_ind = . then hon_prog_ind = 0;
proc freq;
 tables term_code term_code*first_gen_flag;
run;


* The fresh_status8 code now finished off the data set used for student success analysis;
* updated 4/30/2019 to include new SAT scores and BESTR and AValue;
Data Fresh_status8;
 set Fresh_status7c;
If Postbacc_type = '' then Postbacc_type = 'NULL';
If final_gpa = . then final_gpa = final_gpa1;
If sat_i_comp ne . then sat_i = 1; else sat_i = 0;
If high_school_gpa ne . then hsgpa = 1 ; else hsgpa = 0;
If Act_comp = 36  then Sat_i_comp1 =  	1600;
If Act_comp = 35 then Sat_i_comp1 =  	1560;
If Act_comp = 34 then Sat_i_comp1 =  	1510;
If Act_comp = 33 then Sat_i_comp1 =  	1460;
If Act_comp = 32 then Sat_i_comp1 =  	1420;
If Act_comp = 31 then Sat_i_comp1 =  	1380;
If Act_comp = 30 then Sat_i_comp1 =  	1340;
If Act_comp = 29 then Sat_i_comp1 =  	1300;
If Act_comp = 28 then Sat_i_comp1 =  	1260;
If Act_comp = 27 then Sat_i_comp1 =  	1220;
If Act_comp = 26 then Sat_i_comp1 =  	1190;
If Act_comp = 25 then Sat_i_comp1 =  	1150;
If Act_comp = 24 then Sat_i_comp1 =  	1110;
If Act_comp = 23 then Sat_i_comp1 =  	1070;
If Act_comp = 22 then Sat_i_comp1 =  	1030;
If Act_comp = 21 then Sat_i_comp1 =  	990;
If Act_comp = 20 then Sat_i_comp1 =  	950;
If Act_comp = 19 then Sat_i_comp1 =  	910;
If Act_comp = 18 then Sat_i_comp1 =  	870;
If Act_comp = 17 then Sat_i_comp1 =  	830;
If Act_comp = 16 then Sat_i_comp1 =  	790;
If Act_comp = 15 then Sat_i_comp1 =  	740;
If Act_comp = 14 then Sat_i_comp1 =  	690;
If Act_comp = 13 then Sat_i_comp1 =  	640;
If Act_comp = 12 then Sat_i_comp1 =  	590;
If Act_comp = 11 then Sat_i_comp1 =  	530;
If SAT_i_comp > Sat_i_comp1 then Best1 = SAT_i_comp;
If SAT_i_comp < Sat_i_comp1 then Best1 = SAT_i_comp1;
IF best = . then best = best1;
If qvalue = . then qvalue = best + (high_school_gpa * 400) ;
If Yr2_cont = 1 or Yr2_grad = 1 then Yr2_Success = 1; else Yr2_success = 0;
If First_gen_flag ne 'Y' then First_gen_flag = 'N';
If degree_term_code ne . then graduate = 1 ; else graduate = 0;
If final_gpa lt 2.0 then WSU_GPA = 'b0.0 - 1.999';
If final_gpa ge 2.0 and final_gpa lt 2.5 then WSU_GPA = 'c2.0 - 2.499';
If final_gpa ge 2.5 and final_gpa lt 3 then WSU_GPA =   'd2.5 - 3.000';
If final_gpa ge 3   and final_gpa lt 3.5 then WSU_GPA = 'e3.0 - 3.500';
If final_gpa ge 3.5 and final_gpa le 4 then WSU_GPA =   'h3.5 - 4.000';
If final_gpa = . then WSU_GPA =    						'a       None';
if final_gpa = 0 then WSU_GPA = 						'a       None';

If high_school_gpa lt  2.0 then HS_GPA = 'b0.0 - 1.999';
If high_school_gpa ge 2.0 and high_school_gpa lt 2.5 then HS_GPA = 'c2.0 - 2.499';
If high_school_gpa ge 2.5 and high_school_gpa lt 3 then HS_GPA =   'd2.5 - 3.000';
If high_school_gpa ge 3   and high_school_gpa lt 3.1 then HS_GPA = 'e3.0 - 3.099';
If high_school_gpa ge 3.1   and high_school_gpa lt 3.2 then HS_GPA = 'f3.10 - 3.199';
If high_school_gpa ge 3.2   and high_school_gpa lt 3.3 then HS_GPA = 'g3.20 - 3.299';
If high_school_gpa ge 3.3   and high_school_gpa lt 3.4 then HS_GPA = 'h3.30 - 3.399';
If high_school_gpa ge 3.4   and high_school_gpa lt 3.5 then HS_GPA = 'i3.40 - 3.499';
If high_school_gpa ge 3.5 and high_school_gpa le 4 then HS_GPA =   'j3.5 - 4.000';
If high_school_gpa = . then HS_GPA =    'a            None';

If high_school_gpa lt  2.0 then HS_GPA1 = 'b0.0 - 1.999';
If high_school_gpa ge 2.0 and high_school_gpa lt 2.5 then HS_GPA1 = 'c2.0 - 2.499';
If high_school_gpa ge 2.5 and high_school_gpa lt 3 then HS_GPA1 =   'd2.5 - 2.999';
If high_school_gpa ge 3   and high_school_gpa lt 3.5 then HS_GPA1 = 'e3.0 - 3.499';
If high_school_gpa ge 3.5 and high_school_gpa le 4 then HS_GPA1 =   'f3.5 - 4.000';
If high_school_gpa = . then HS_GPA1 =    'a            None';

If high_school_gpa lt  2.0 then HS_GPA2 = 'b0.0 - 1.999';
If high_school_gpa ge 2.0 and high_school_gpa lt 2.5 then HS_GPA2 = 'c2.0 - 2.499';
If high_school_gpa ge 2.5 and high_school_gpa lt 3 then HS_GPA2 =   'd2.5 - 3.000';
If high_school_gpa ge 3   and high_school_gpa lt 3.1 then HS_GPA2 = 'e3.0 - 3.099';
If high_school_gpa ge 3.1 and high_school_gpa lt 3.2 then HS_GPA2 = 'f3.10 - 3.199';
If high_school_gpa ge 3.2 and high_school_gpa lt 3.3 then HS_GPA2 = 'g3.20 - 3.299';
If high_school_gpa ge 3.3 and high_school_gpa lt 3.4 then HS_GPA2 = 'h3.30 - 3.399';
If high_school_gpa ge 3.4 and high_school_gpa lt 3.5 then HS_GPA2 = 'i3.40 - 3.499';
If high_school_gpa ge 3.5 and high_school_gpa lt 3.8 then HS_GPA2 =   'j3.5 - 3.799';
If high_school_gpa ge 3.8 and high_school_gpa le 4.0 then HS_GPA2 =   'k3.8 - 4.000';
If high_school_gpa = . then HS_GPA2 =    'a            None';

If high_school_gpa lt 2.5                               then HS_GPA8 =  'b0.0 - 2.499';
If high_school_gpa ge 2.5  and high_school_gpa lt 2.6   then HS_GPA8 =   'c2.5 - 2.599';
If high_school_gpa ge 2.6  and high_school_gpa lt 2.75  then HS_GPA8 =   'd2.6 - 2.749';
If high_school_gpa ge 2.75 and high_school_gpa lt 2.9   then HS_GPA8 =   'e2.75- 2.899';
If high_school_gpa ge 2.9  and high_school_gpa lt 3.0   then HS_GPA8 =   'f2.9 - 2.999';
If high_school_gpa ge 3.0  and high_school_gpa lt 3.1   then HS_GPA8 =   'g3.0 - 3.099';
If high_school_gpa ge 3.1  and high_school_gpa lt 3.2   then HS_GPA8 =   'h3.1 - 3.199';
If high_school_gpa ge 3.2  and high_school_gpa lt 3.3   then HS_GPA8 =   'i3.2 - 3.299';
If high_school_gpa ge 3.3  and high_school_gpa lt 3.4   then HS_GPA8 =   'j3.3 - 3.399';
If high_school_gpa ge 3.4  and high_school_gpa le 3.5   then HS_GPA8 =   'k3.4 - 3.499';
If high_school_gpa ge 3.5  and high_school_gpa le 3.6   then HS_GPA8 =   'l3.5 - 3.599';
If high_school_gpa ge 3.6  and high_school_gpa le 3.8  then HS_GPA8 =   'm3.6 - 3.799';
If high_school_gpa ge 3.8                              then HS_GPA8 =   'n > 3.8     ';
If high_school_gpa = . then HS_GPA8 =    'a            None';

If high_school_gpa lt 2.5                               then HS_GPA10 =  'b0.0 - 2.499';
If high_school_gpa ge 2.5  and high_school_gpa lt 2.8   then HS_GPA10 =   'c2.5 - 2.799';
If high_school_gpa ge 2.8  and high_school_gpa lt 3.0   then HS_GPA10 =   'd2.8 - 2.999';
If high_school_gpa ge 3.0  and high_school_gpa lt 3.1   then HS_GPA10 =   'e3.0 - 3.099';
If high_school_gpa ge 3.1  and high_school_gpa lt 3.2   then HS_GPA10 =   'f3.1 - 3.199';
If high_school_gpa ge 3.2  and high_school_gpa lt 3.3   then HS_GPA10 =   'g3.2 - 3.299';
If high_school_gpa ge 3.3  and high_school_gpa lt 3.4   then HS_GPA10 =   'h3.3 - 3.399';
If high_school_gpa ge 3.4  and high_school_gpa le 3.5   then HS_GPA10 =   'i3.4 - 3.499';
If high_school_gpa ge 3.5  and high_school_gpa le 3.8   then HS_GPA10 =   'j3.5 - 3.799';
If high_school_gpa ge 3.8                              then HS_GPA10 =   'l > 3.8     ';
If high_school_gpa = . then HS_GPA10 =    'a            None';

If high_school_gpa lt 2.5                               then HS_GPA9 =   'b0.0 - 2.499';
If high_school_gpa ge 2.5  and high_school_gpa lt 2.6   then HS_GPA9 =   'c2.5 - 2.599';
If high_school_gpa ge 2.6  and high_school_gpa lt 2.7   then HS_GPA9 =   'd2.6 - 2.699';
If high_school_gpa ge 2.7  and high_school_gpa lt 2.8   then HS_GPA9 =   'e2.7 - 2.799';
If high_school_gpa ge 2.8  and high_school_gpa lt 2.9   then HS_GPA9 =   'f2.8 - 2.899';
If high_school_gpa ge 2.9  and high_school_gpa lt 2.95  then HS_GPA9 =   'g2.9 - 2.949';
If high_school_gpa ge 2.95 and high_school_gpa lt 3.0   then HS_GPA9 =   'h2.95- 2.999';
If high_school_gpa ge 3.0  and high_school_gpa lt 3.1   then HS_GPA9 =   'i3.0 - 3.099';
If high_school_gpa ge 3.1  and high_school_gpa lt 3.2   then HS_GPA9 =   'j3.1 - 3.199';
If high_school_gpa ge 3.2  and high_school_gpa lt 3.3   then HS_GPA9 =   'k3.2 - 3.299';
If high_school_gpa ge 3.3  and high_school_gpa lt 3.4   then HS_GPA9 =   'l3.3 - 3.399';
If high_school_gpa ge 3.4  and high_school_gpa le 3.5   then HS_GPA9 =   'm3.4 - 3.499';
If high_school_gpa ge 3.5  and high_school_gpa le 3.6   then HS_GPA9 =   'n3.5 - 3.599';
If high_school_gpa ge 3.6  and high_school_gpa le 3.7  then HS_GPA9 =   'o3.6 - 3.699';
If high_school_gpa ge 3.7  and high_school_gpa le 3.8  then HS_GPA9 =   'p3.7 - 3.799';
If high_school_gpa ge 3.8  and high_school_gpa le 3.9  then HS_GPA9 =   'q3.8 - 3.899';
If high_school_gpa ge 3.9                              then HS_GPA9 =   'r > 3.9     ';
If high_school_gpa = . then HS_GPA9 =    'a            None';


If high_school_gpa lt  2.0 then HS_GPA9a = 'b0.0 - 1.999';
If high_school_gpa ge 2.0 and high_school_gpa lt 2.5 then HS_GPA9a = 'c2.0 - 2.499';
If high_school_gpa ge 2.5 and high_school_gpa lt 3 then HS_GPA9a =   'd2.5 - 3.000';
If high_school_gpa ge 3   and high_school_gpa lt 3.1 then HS_GPA9a = 'e3.0 - 3.099';
If high_school_gpa ge 3.1 and high_school_gpa lt 3.2 then HS_GPA9a = 'f3.10 - 3.199';
If high_school_gpa ge 3.2 and high_school_gpa lt 3.3 then HS_GPA9a = 'g3.20 - 3.299';
If high_school_gpa ge 3.3 and high_school_gpa lt 3.4 then HS_GPA9a = 'h3.30 - 3.399';
If high_school_gpa ge 3.4 and high_school_gpa lt 3.5 then HS_GPA9a = 'i3.40 - 3.499';
If high_school_gpa ge 3.5 and high_school_gpa lt 3.75 then HS_GPA9a =   'j3.5 - 3.749';
If high_school_gpa ge 3.75 and high_school_gpa le 4.0 then HS_GPA9a =   'k3.75 - 4.000';
If high_school_gpa = . then HS_GPA9a =    'a            None';

If high_school_gpa lt  2.5 then HS_GPA3 =                           'a < 2.5     ';
If high_school_gpa ge 2.5 and high_school_gpa lt 2.75 then HS_GPA3 ='b2.5 - 2.749';
If high_school_gpa ge 2.75 and high_school_gpa lt 3 then HS_GPA3 =  'c2.75 - 3.00';
If high_school_gpa ge 3   and high_school_gpa lt 3.2 then HS_GPA3 = 'd3.0 - 3.199';
If high_school_gpa ge 3.2 and high_school_gpa lt 3.4 then HS_GPA3 = 'e3.20 - 3.39';
If high_school_gpa ge 3.4 and high_school_gpa lt 3.6 then HS_GPA3 = 'f3.40 - 3.59';
If high_school_gpa ge 3.6 and high_school_gpa lt 3.8 then HS_GPA3 = 'g3.60 - 3.79';
If high_school_gpa ge 3.8 and high_school_gpa le 4.0 then HS_GPA3 = 'h3.80 - 4.00';
If high_school_gpa = . then HS_GPA3 =    'a            None';

*Use this one for at risk students;
If high_school_gpa lt 3.0 then GPA_Risk = 1;
If high_school_gpa ge 3.0 then GPA_Risk = 0;
If high_school_gpa = .    then GPA_Risk = .;

*Use this one for honors;
If high_school_gpa lt  3.8 then HS_GPA4 = 'b0.0 - 3.79';
If high_school_gpa ge 3.8 and high_school_gpa le 3.9 then HS_GPA4 = 'c3.8 - 3.89';
If high_school_gpa ge 3.9 then HS_GPA4 =   'd3.9 - 4.00';
If high_school_gpa = . then HS_GPA4 =    'a            None';


If per_eligible_lunch le  20 then lunch = 'z0.0 - 20%';
If per_eligible_lunch gt 20 and per_eligible_lunch le 30 then lunch = 'b21% - 30%';
If per_eligible_lunch gt 30 and per_eligible_lunch le 40 then lunch =   'c31% - 40%';
If per_eligible_lunch gt 40 and per_eligible_lunch le 50 then lunch = 'd41%- 50%';
If per_eligible_lunch gt 50 then lunch =    'e > 50%   ';
If per_eligible_lunch = . then lunch = '';

If best < 900 then best_score =                  'b < 900  ';
If best ge  900 and best < 1000 then best_score = 'c 900-999 ';
If best ge 1000 and best < 1100 then best_score = 'd1000-1099';
If best ge 1100 and best < 1200 then best_score = 'e1100-1199';
If best ge 1200 and best < 1300 then best_score = 'f1200-1299';
If best ge 1300 then best_score =                 'g > 1300  '; 
If best = . then best_score =                     'a     None';

If best < 800 then best_score2 =                  'b < 800  ';
If best ge  800 and best < 900  then best_score2 = 'c 800-899 ';
If best ge  900 and best < 1000 then best_score2 = 'd 900- 999';
If best ge 1000 and best < 1100 then best_score2 = 'e1000-1099';
If best ge 1100 and best < 1200 then best_score2 = 'f1100-1199';
If best ge 1200 and best < 1300 then best_score2 = 'g1200-1299';
If best ge 1300 then best_score2 =                 'h > 1300  '; 
If best = . then best_score2 =                     'a     None';

If best < 900 then best_score1 =                  'b < 900  ';
If best ge  900 and best < 1000 then best_score1 = 'c 900-999 ';
If best ge 1000 and best < 1100 then best_score1 = 'd1000-1099';
If best ge 1100 and best < 1200 then best_score1 = 'e1100-1199';
If best ge 1200 then best_score1 =                 'f > 1200  '; 
If best = . then best_score1 =                     'a     None';


If bestr < 900 then bestr_score =                  'b < 900  ';
If bestr ge  900 and bestr < 1000 then bestr_score = 'c 900-999 ';
If bestr ge 1000 and bestr < 1100 then bestr_score = 'd1000-1099';
If bestr ge 1100 and bestr < 1200 then bestr_score = 'e1100-1199';
If bestr ge 1200 and bestr < 1300 then bestr_score = 'f1200-1299';
If bestr ge 1300 then bestr_score =                 'g > 1300  '; 
If bestr = . then bestr_score =                     'a     None';

If bestr < 800 then bestr_score2 =                  'b < 800  ';
If bestr ge  800 and bestr < 900  then bestr_score2 = 'c 800-899 ';
If bestr ge  900 and bestr < 1000 then bestr_score2 = 'd 900- 999';
If bestr ge 1000 and bestr < 1100 then bestr_score2 = 'e1000-1099';
If bestr ge 1100 and bestr < 1200 then bestr_score2 = 'f1100-1199';
If bestr ge 1200 and bestr < 1300 then bestr_score2 = 'g1200-1299';
If bestr ge 1300 then bestr_score2 =                 'h > 1300  '; 
If bestr = . then bestr_score2 =                     'a     None';

If bestr < 900 then bestr_score1 =                  'b < 900  ';
If bestr ge  900 and bestr < 1000 then bestr_score1 = 'c 900-999 ';
If bestr ge 1000 and bestr < 1100 then bestr_score1 = 'd1000-1099';
If bestr ge 1100 and bestr < 1200 then bestr_score1 = 'e1100-1199';
If bestr ge 1200 then bestr_score1 =                 'f > 1200  '; 
If bestr = . then bestr_score1 =                     'a     None';

If qvalue < 1900 					then qvalue_cat = 'bLess than 1900';
If qvalue ge 1900 and qvalue < 2000 then qvalue_cat = 'c  1900 to 2000';
If qvalue ge 2000 and qvalue < 2100	then qvalue_cat = 'd  2000 to 2100';
*If qvalue < 2100 then qvalue_cat =                    'd < 2100       ';
If qvalue ge 2100 and qvalue < 2200 then qvalue_cat = 'e  2100 to 2199';
If qvalue ge 2200 and qvalue < 2300 then qvalue_cat = 'f  2200 to 2299';
If qvalue ge 2300 and qvalue < 2400 then qvalue_cat = 'g  2300 to 2399';
If qvalue ge 2400 and qvalue < 2500 then qvalue_cat = 'h  2400 to 2499';
If qvalue ge 2500 and qvalue < 2600 then qvalue_cat = 'i  2500 to 2599';
If qvalue ge 2600 and qvalue < 2750 then qvalue_cat = 'j  2600 to 2749';
If qvalue ge 2750 then qvalue_cat = 'k  2750 or more';
if qvalue = . then qvalue_cat = 					  'a          None';

If qvalue < 2100 then qvalue_cat2 =                     'd < 2100       ';
If qvalue ge 2100 and qvalue < 2200 then qvalue_cat2 = 'e  2100 to 2199';
If qvalue ge 2200 and qvalue < 2300 then qvalue_cat2 = 'f  2200 to 2299';
If qvalue ge 2300 and qvalue < 2400 then qvalue_cat2 = 'g  2300 to 2399';
If qvalue ge 2400 and qvalue < 2500 then qvalue_cat2 = 'h  2400 to 2499';
If qvalue ge 2500 and qvalue < 2600 then qvalue_cat2 = 'i  2500 to 2599';
If qvalue ge 2600 and qvalue < 2700 then qvalue_cat2 = 'j  2600 to 2699';
If qvalue ge 2700 and qvalue < 2800 then qvalue_cat2 = 'k  2700 to 2799';
If qvalue ge 2800 then qvalue_cat2 = 'k  2800 or more';
if qvalue = . then qvalue_cat2 = 					  'a          None';

If qvalue < 2100 then qvalue_cat3 =                     'b < 2100       ';
If qvalue ge 2100 and qvalue < 2200 then qvalue_cat3 = 'c  2100 to 2199';
If qvalue ge 2200 and qvalue < 2300 then qvalue_cat3 = 'd  2200 to 2299';
If qvalue ge 2300 and qvalue < 2400 then qvalue_cat3 = 'e  2300 to 2399';
If qvalue ge 2400 and qvalue < 2600 then qvalue_cat3 = 'f  2400 to 2599';
If qvalue ge 2600 then qvalue_cat3 = 'g  2600 or more';
if qvalue = . then qvalue_cat3 = 					  'a          None';

If qvalue < 1800 then qvalue_cat4 =                     'b < 1800       ';
If qvalue ge 1800 and qvalue < 1850 then qvalue_cat4 = 'c  1800 to 1849';
If qvalue ge 1850 and qvalue < 1900 then qvalue_cat4 = 'd  1850 to 1900';
If qvalue ge 1900 then qvalue_cat4 = 'g  1900 or more';
if qvalue = . then qvalue_cat4 = 					  'a          None';

*For honors;
If qvalue < 2700 then qvalue_cat5 =                     'b < 2700       ';
If qvalue ge 2700 and qvalue < 2800 then qvalue_cat5 = 'c  2700 to 2799';
If qvalue ge 2800 and qvalue < 2900 then qvalue_cat5 = 'd  2800 to 2899';
If qvalue ge 2900 then qvalue_cat5 = 'e  2900 or more';
if qvalue = . then qvalue_cat5 = 					  'a          None';


If avalue < 1900 					then avalue_cat = 'bLess than 1900';
If avalue ge 1900 and avalue < 2000 then avalue_cat = 'c  1900 to 2000';
If avalue ge 2000 and avalue < 2100	then avalue_cat = 'd  2000 to 2100';
*If avalue < 2100 then avalue_cat =                    'd < 2100       ';
If avalue ge 2100 and avalue < 2200 then avalue_cat = 'e  2100 to 2199';
If avalue ge 2200 and avalue < 2300 then avalue_cat = 'f  2200 to 2299';
If avalue ge 2300 and avalue < 2400 then avalue_cat = 'g  2300 to 2399';
If avalue ge 2400 and avalue < 2500 then avalue_cat = 'h  2400 to 2499';
If avalue ge 2500 and avalue < 2600 then avalue_cat = 'i  2500 to 2599';
If avalue ge 2600 and avalue < 2750 then avalue_cat = 'j  2600 to 2749';
If avalue ge 2750 then avalue_cat = 'k  2750 or more';
if avalue = . then avalue_cat = 					  'a          None';

If avalue < 2100 then avalue_cat2 =                     'd < 2100       ';
If avalue ge 2100 and avalue < 2200 then avalue_cat2 = 'e  2100 to 2199';
If avalue ge 2200 and avalue < 2300 then avalue_cat2 = 'f  2200 to 2299';
If avalue ge 2300 and avalue < 2400 then avalue_cat2 = 'g  2300 to 2399';
If avalue ge 2400 and avalue < 2500 then avalue_cat2 = 'h  2400 to 2499';
If avalue ge 2500 and avalue < 2600 then avalue_cat2 = 'i  2500 to 2599';
If avalue ge 2600 and avalue < 2700 then avalue_cat2 = 'j  2600 to 2699';
If avalue ge 2700 and avalue < 2800 then avalue_cat2 = 'k  2700 to 2799';
If avalue ge 2800 then avalue_cat2 = 'k  2800 or more';
if avalue = . then avalue_cat2 = 					  'a          None';

If avalue < 2100 then avalue_cat3 =                     'b < 2100       ';
If avalue ge 2100 and avalue < 2200 then avalue_cat3 = 'c  2100 to 2199';
If avalue ge 2200 and avalue < 2300 then avalue_cat3 = 'd  2200 to 2299';
If avalue ge 2300 and avalue < 2400 then avalue_cat3 = 'e  2300 to 2399';
If avalue ge 2400 and avalue < 2600 then avalue_cat3 = 'f  2400 to 2599';
If avalue ge 2600 then avalue_cat3 = 'g  2600 or more';
if avalue = . then avalue_cat3 = 					  'a          None';

If avalue < 1800 then avalue_cat4 =                     'b < 1800       ';
If avalue ge 1800 and avalue < 1850 then avalue_cat4 = 'c  1800 to 1849';
If avalue ge 1850 and avalue < 1900 then avalue_cat4 = 'd  1850 to 1900';
If avalue ge 1900 then avalue_cat4 = 'g  1900 or more';
if avalue = . then avalue_cat4 = 					  'a          None';

*For honors;
If avalue < 2700 then avalue_cat5 =                     'b < 2700       ';
If avalue ge 2700 and avalue < 2800 then avalue_cat5 = 'c  2700 to 2799';
If avalue ge 2800 and avalue < 2900 then avalue_cat5 = 'd  2800 to 2899';
If avalue ge 2900 then avalue_cat5 = 'e  2900 or more';
if avalue = . then avalue_cat5 = 					  'a          None';


if fed_need_yr1 ge 0 then file_fafsa = 1; else file_fafsa = 0;
if total_disb_yr1 = . then total_disb_yr1 = 0;
if total_accept_yr1 = . then total_accept_yr1 = 0;
if total_offer_yr1 = . then total_offer_yr1 = 0;

if total_disb_yr2 = . then total_disb_yr2 = 0;
if total_accept_yr2 = . then total_accept_yr2 = 0;
if total_offer_yr2 = . then total_offer_yr2 = 0;

if total_disb_yr3 = . then total_disb_yr3 = 0;
if total_accept_yr3 = . then total_accept_yr3 = 0;
if total_offer_yr3 = . then total_offer_yr3 = 0;

if total_disb_yr4 = . then total_disb_yr4 = 0;
if total_accept_yr4 = . then total_accept_yr4 = 0;
if total_offer_yr4 = . then total_offer_yr4 = 0;

if total_disb_yr5 = . then total_disb_yr5 = 0;
if total_accept_yr5 = . then total_accept_yr5 = 0;
if total_offer_yr5 = . then total_offer_yr5 = 0;

if total_disb_yr6 = . then total_disb_yr6 = 0;
if total_accept_yr6 = . then total_accept_yr6 = 0;
if total_offer_yr6 = . then total_offer_yr6 = 0;


unmet_need_disb_yr1 = fed_need_yr1 - total_disb_yr1;
unmet_need_acpt_yr1 = fed_need_yr1 - total_accept_yr1;
unmet_need_ofr_yr1 = fed_need_yr1 - total_offer_yr1;
unmet_need_acpt_xPerkins_yr1 = unmet_need_acpt_yr1 + Perkins_yr1;

unmet_need_disb_yr2 = fed_need_yr2 - total_disb_yr2;
unmet_need_acpt_yr2 = fed_need_yr2 - total_accept_yr2;
unmet_need_ofr_yr2 = fed_need_yr2 - total_offer_yr2;
unmet_need_acpt_xPerkins_yr2 = unmet_need_acpt_yr2 + Perkins_yr2;

unmet_need_disb_yr3 = fed_need_yr3 - total_disb_yr3;
unmet_need_acpt_yr3 = fed_need_yr3 - total_accept_yr3;
unmet_need_ofr_yr3 = fed_need_yr3 - total_offer_yr3;
unmet_need_acpt_xPerkins_yr3 = unmet_need_acpt_yr3 + Perkins_yr3;

unmet_need_disb_yr4 = fed_need_yr4 - total_disb_yr4;
unmet_need_acpt_yr4 = fed_need_yr4 - total_accept_yr4;
unmet_need_ofr_yr4 = fed_need_yr4 - total_offer_yr4;
unmet_need_acpt_xPerkins_yr4 = unmet_need_acpt_yr4 + Perkins_yr4;

unmet_need_disb_yr5 = fed_need_yr5 - total_disb_yr5;
unmet_need_acpt_yr5 = fed_need_yr5 - total_accept_yr5;
unmet_need_ofr_yr5 = fed_need_yr5 - total_offer_yr5;
unmet_need_acpt_xPerkins_yr5 = unmet_need_acpt_yr5 + Perkins_yr5;

unmet_need_disb_yr6 = fed_need_yr6 - total_disb_yr6;
unmet_need_acpt_yr6 = fed_need_yr6 - total_accept_yr6;
unmet_need_ofr_yr6 = fed_need_yr6 - total_offer_yr6;
unmet_need_acpt_xPerkins_yr6 = unmet_need_acpt_yr6 + Perkins_yr6;


Free_Red_Lunch_Percent = per_eligible_lunch * 0.01;

if fed_need_yr1 = . then fed_need_check = 1 ; else fed_need_check = 0 ; 

If unmet_need_disb_yr1 le 0  then stated_unmet_need_disb_yr1 =                        'b $0.00       ';
If unmet_need_disb_yr1 gt 0 and unmet_need_disb_yr1 < 1000 then stated_unmet_need_disb_yr1 =                        'c< $1000      ';
If unmet_need_disb_yr1 ge 1000 and unmet_need_disb_yr1 lt 7000 then stated_unmet_need_disb_yr1 = 'd$1000 - $6999';
If unmet_need_disb_yr1 ge 7000 then stated_unmet_need_disb_yr1 =    'e > $7000   ';
If unmet_need_disb_yr1 = . then stated_unmet_need_disb_yr1 = 'a None';

If unmet_need_acpt_yr1 le  0  									then stated_unmet_need_acpt_yr1 = 'b $0.00       ';
If unmet_need_acpt_yr1 gt 0 and unmet_need_acpt_yr1 < 1000 		then stated_unmet_need_acpt_yr1 = 'c< $1000      ';
If unmet_need_acpt_yr1 ge 1000 and unmet_need_acpt_yr1 lt 7000 	then stated_unmet_need_acpt_yr1 = 'd$1000 - $6999';
If unmet_need_acpt_yr1 ge 7000 									then stated_unmet_need_acpt_yr1 = 'e > $7000   ';
If unmet_need_acpt_yr1 = . 										then stated_unmet_need_acpt_yr1 = 'a None';

If unmet_need_acpt_xPerkins_yr1 le  0  												then stated_unmet_need_acpt_xPyr1 = 'b $0.00       ';
If unmet_need_acpt_xPerkins_yr1 gt 0 and unmet_need_acpt_xPerkins_yr1 < 1000 		then stated_unmet_need_acpt_xPyr1 = 'c< $1000      ';
If unmet_need_acpt_xPerkins_yr1 ge 1000 and unmet_need_acpt_xPerkins_yr1 lt 7000 	then stated_unmet_need_acpt_xPyr1 = 'd$1000 - $6999';
If unmet_need_acpt_xPerkins_yr1 ge 7000 											then stated_unmet_need_acpt_xPyr1 = 'e > $7000   ';
If unmet_need_acpt_xPerkins_yr1 = . 												then stated_unmet_need_acpt_xPyr1 = 'a None';

If unmet_need_ofr_yr1 le 0  									then stated_unmet_need_ofr_yr1 =  'b $0.00       ';
If unmet_need_ofr_yr1 ge 0 and unmet_need_ofr_yr1 < 1000 		then stated_unmet_need_ofr_yr1 =  'c< $1000      ';
If unmet_need_ofr_yr1 ge 1000 and unmet_need_ofr_yr1 lt 7000 	then stated_unmet_need_ofr_yr1 =  'd$1000 - $6999';
If unmet_need_ofr_yr1 ge 7000 									then stated_unmet_need_ofr_yr1 =  'e > $7000   ';
If unmet_need_ofr_yr1 = . 										then stated_unmet_need_ofr_yr1 =  'a None';

unmet_need_thosewneed_yr1 = unmet_need_acpt_yr1;
if unmet_need_acpt_yr1 le 0 then unmet_need_thosewneed_yr1 = .;

unmet_need_thosewneed_d_yr1 = unmet_need_disb_yr1;
if unmet_need_disb_yr1 le 0 then unmet_need_thosewneed_d_yr1 = .;

IF term_code ge 20163 then secyrret = 0; else secyrret = 1; *anyone admitted aftr fall 2016 can't have second yr reten yet;
IF term_code ge 20153 then thrdyrret = 0; else thrdyrret = 1; * anyone admitted after fall 2011 can't have third yr reten yet;
If term_code ge 20133 then FourYrRate = 0; else FourYrRate = 1; *Finding only those who would have 4 yr grad data;
If term_code ge 20113 then FiveYrRate = 0; else FiveYrRate = 1; *Finding only those who would have 5 yr grad data;
If term_code ge 20113 then SixYrRate = 0; else SixYrRate = 1; *Finding only those who would have 6 yr grad data;
If Yr1_grad + Yr2_grad + Yr3_grad + Yr4_grad ge 1 then FourYrGrad = 1; else FourYrGrad = 0;
If Yr1_grad + Yr2_grad + Yr3_grad + Yr4_grad + Yr5_grad ge 1 then FiveYrGrad = 1; else FiveYrGrad = 0;
If Yr1_grad + Yr2_grad + Yr3_grad + Yr4_grad + Yr5_grad + Yr6_grad ge 1 then SixYrGrad = 1; else SixYrGrad = 0;

If degree_term_code ne . then graduate = 1; else graduate = 0;

If Yr6_grad = 0 and Yr7_Not_enroll = 1 then StillEnrl7yr = 0 ;
If Yr6_grad = 0 and Yr7_cont = 1 then StillEnrl7yr = 1 ;
If Yr6_grad = 1 then StillEnrl7yr = 2 ;

If Yr5_grad = 0 and Yr6_Not_enroll = 1 then StillEnrl6yr = 0 ;
If Yr5_grad = 0 and Yr6_cont = 1 then StillEnrl6yr = 1 ;
If Yr5_grad = 1 then StillEnrl6yr = 2 ; 

If Yr4_Grad = 0 and Yr5_Not_enroll = 1 then StillEnrl5yr = 0 ;
If Yr4_Grad = 0 and Yr5_cont = 1 then StillEnrl5yr = 1 ; 
If Yr4_Grad = 1 then StillEnrl5yr = 2 ;

If Yr3_Grad = 0 and Yr4_Not_enroll = 1 then StillEnrl4yr = 0 ;
If Yr3_Grad = 0 and Yr4_cont = 1 then StillEnrl4yr = 1 ; 
If Yr3_Grad = 1 then StillEnrl4yr = 2 ;

If term_code = 20133 then f2013 = 1; else f2013 = 0;
If term_code = 20123 then f2012 = 1; else f2012 = 0;
If term_code = 20113 then f2011 = 1; else f2011 = 0;
If term_code = 20103 then f2010 = 1; else f2010 = 0;
If term_code = 20093 then f2009 = 1; else f2009 = 0;
If term_code = 20083 then f2008 = 1; else f2008 = 0;
If term_code = 20073 then f2007 = 1; else f2007 = 0;

if aid_year = '2007' then fasfa_deadline1 =   '16FEB2006:00:00:00'd ;
if aid_year = '2007' then fasfa_deadline2 =   '01JUL2006:00:00:00'd ;
if aid_year = '2007' then fasfa_deadline3 =   '01AUG2006:00:00:00'd ;
if aid_year = '2008' then fasfa_deadline1 =   '16FEB2007:00:00:00'd ;
if aid_year = '2008' then fasfa_deadline2 =   '01JUL2007:00:00:00'd ;
if aid_year = '2008' then fasfa_deadline3 =   '01AUG2007:00:00:00'd ;
if aid_year = '2009' then fasfa_deadline1 =   '16FEB2008:00:00:00'd ;
if aid_year = '2009' then fasfa_deadline2 =   '01JUL2008:00:00:00'd ;
if aid_year = '2009' then fasfa_deadline3 =   '01AUG2008:00:00:00'd ;
if aid_year = '2010' then fasfa_deadline1 =   '16FEB2009:00:00:00'd ;
if aid_year = '2010' then fasfa_deadline2 =   '01JUL2009:00:00:00'd ;
if aid_year = '2010' then fasfa_deadline3 =   '01AUG2009:00:00:00'd ;
if aid_year = '2011' then fasfa_deadline1 =   '16FEB2010:00:00:00'd ;
if aid_year = '2011' then fasfa_deadline2 =   '01JUL2010:00:00:00'd ;
if aid_year = '2011' then fasfa_deadline3 =   '01AUG2010:00:00:00'd ;
if aid_year = '2012' then fasfa_deadline1 =   '16FEB2011:00:00:00'd ;
if aid_year = '2012' then fasfa_deadline2 =   '01JUL2011:00:00:00'd ;
if aid_year = '2012' then fasfa_deadline3 =   '01AUG2011:00:00:00'd ;
if aid_year = '2013' then fasfa_deadline1 =   '16FEB2012:00:00:00'd ;
if aid_year = '2013' then fasfa_deadline2 =   '01JUL2012:00:00:00'd ;
if aid_year = '2013' then fasfa_deadline3 =   '01AUG2012:00:00:00'd ;
if aid_year = '2014' then fasfa_deadline1 =   '16FEB2013:00:00:00'd ;
if aid_year = '2014' then fasfa_deadline2 =   '01JUL2013:00:00:00'd ;
if aid_year = '2014' then fasfa_deadline3 =   '01AUG2013:00:00:00'd ;
if aid_year = '2015' then fasfa_deadline1 =   '16FEB2014:00:00:00'd ;
if aid_year = '2015' then fasfa_deadline2 =   '01JUL2014:00:00:00'd ;
if aid_year = '2015' then fasfa_deadline3 =   '01AUG2014:00:00:00'd ;

dayssince_deadline1  = FAFSADate_yr1 - fasfa_deadline1;
dayssince_deadline2  = FAFSADate_yr1 - fasfa_deadline2;
dayssince_deadline3  = FAFSADate_yr1 - fasfa_deadline3;
If dayssince_deadline1 < 0 then file_date                               = 'aBefore Feb 16';
If dayssince_deadline1 ge 0  and dayssince_deadline2 < 0 then file_date = 'bBefore Ju1 01';
If dayssince_deadline2 ge 0  and dayssince_deadline3 < 0 then file_date = 'cBefore Aug 01';
If dayssince_deadline3 ge 0  then file_date                             = 'dAfter  Aug 01';
If FAFSADate_yr1 = .  then file_date = 'e No FASFA   ';


Program1 = UAA_yr1 + CAA_yr1 ;
If Program1 ge 1 then Program = 1; else Program = 0;

pellandfirstgen = 0;
if first_gen_flag = 'Y' and pell_eligibility_ind = 1 then pellandfirstgen = 1;
minorityandfirstgen = 0;
if ipeds_minority_ind = 1 then minorityandfirstgen = 1;
if first_gen_flag = 'Y' then minorityandfirstgen = 1;
need1 = 'none  ';

if perkins_yr1 > 0 then perkins_rec_yr1 = 1; else perkins_rec_yr1 = 0;
if unsub_loan_tot_Yr1 > 0 then unsub_loan_yr1 = 1 ; else unsub_loan_yr1 = 0;
proc sort;
 by term_code;
run;

data temp;
 set fresh_status8;
if emplid ne '011557310' then delete;
/*if term_code ne 20143 then delete;*/
/*if adj_admit_type not in ('FRS','IRF','IPF') then delete;*/
/*if stated_unmet_need_acpt_yr1 ne 'd$1000 - $6999' then delete;*/
run;


PROC EXPORT DATA=  temp
			OUTFILE= "Z:\Student\Retention and Graduation\Student Retention & Graduation Predictive Models\check12014.xlsx"
			DBMS= xlsx REPLACE;
			sheet='Sheet1';
RUN;


data analysis;
 set fresh_status8;

*If WSU_GPA = 'a       None' then delete;  ** Deleting out all of those that never finished a term;
/*
proc freq;
 tables term_code adj_admit_campus; */
*If thrdyrret = 0 then delete;
*If FourYrRate = 0 then delete; 
*If FiveYrRate = 0 then delete;
*if SixYrRate = 0 then delete;
*If HS_GPA1 ne 'f3.5 - 4.000' then delete;
*If HS_GPA1 ne 'e3.0 - 3.499' then delete;
*If HS_GPA1 ne 'd2.5 - 2.999' then delete;

 *If admit_term1 not in (20073, 20083, 20093, 20103, 20113, 20123, 20133, 20143, 20153, 20163) then delete; 
*if admit_term1 not in (20123, 20133, 20143, 20153) then delete;
*if admit_term1 not in (20101, 20111, 20121, 20131, 20141, 20151) then delete;

*if ipeds_full_part_time = 'P' then delete;
*if pell_eligibility_ind ne 1 then delete;
*if ipeds_full_part_time = 'P' then delete;

 *if need1 = 'none  ' then delete;
*if first_gen_flag ne 'Y' then delete;
*if ipeds_minority_ind ne 1 then delete;
*If minorityandfirstgen ne 1 then delete;
/*if fed_need = . then Need = -1.;*/
/*if fed_need = 0 then Need = 0;*/
/*if fed_need gt 0 then Need = 1;*/

*if pellandfirstgen ne 0 then delete;
*if first_gen_flag ne 'Y' then delete;
*if qvalue_cat = 'a          None' then delete; 
*If WA_Residency ne 'RES' then delete;
*If WA_Residency ne 'NON-D' then delete;

proc freq;
 *Tables  yr2_cont*HS_GPA2 yr3_cont*HS_GPA2 Yr2_cont*Best_score Yr3_cont*Best_score Yr2_cont*Qvalue_cat2 Yr3_cont*Qvalue_cat2  / chisq expected;
 *Tables  StillEnrl7yr*HS_GPA2 StillEnrl7Yr*Best_score StillEnrl7Yr*Qvalue_cat2  / chisq expected;
 *tables Yr2_cont*QValue_cat2;
 *tables yr2_cont*best_score2;
 *tables yr2_cont*HS_GPA10 yr2_cont*QValue_cat2;
 *tables stated_unmet_need_acpt_yr1*term_code;
 tables stated_unmet_need_acpt_yr1*yr2_cont;
 *tables yr2_cont yr3_cont StillEnrl4yr StillEnrl5yr StillEnrl6yr  StillEnrl4yr;
 by term_code;
 where adj_admit_type in ('FRS','IPF','IFR')
 and ipeds_full_time_ind = 1
and term_code in (20073,20083,20093,20103,20113,20123,20133,20143,20153,20163,20173,20183);
run;

data temp;
 set fresh_status8;
*if HS_GPA10 not in ('g3.2 - 3.299','h3.3 - 3.399') then delete;
if admit_term1 not in (20073, 20083, 20093, 20103, 20113, 20123, 20133, 20143, 20153, 20163, 20173, 20183) then delete;
if UAA > 0 then UAA_flag = 1; else UAA_flag = 0;
if CAA > 0 then CAA_flag = 1; else CAA_flag = 0;
proc freq;
 *tables yr2_cont*term_code;
 *where adj_admit_type in ('FRS','IPF','IFR') and ipeds_full_part_time = 'F' and stated_unmet_need_acpt = 'e > $7000   ';
 *tables stated_unmet_need_acpt*term_code ipeds_minority_ind*term_code first_gen_flag*term_code wa_residency*term_code ;
 *where adj_admit_type in ('FRS','IPF','IFR') and ipeds_full_part_time = 'F' ; 
 *tables stated_unmet_need_acpt*yr2_cont*term_code ipeds_minority_ind*yr2_cont*term_code first_gen_flag*yr2_cont*term_code wa_residency*yr2_cont*term_code ;
 *where adj_admit_type in ('FRS','IPF','IFR') and ipeds_full_part_time = 'F' ; 
 tables caa_flag*term_code CAA_flag*yr2_cont*term_code;
 where adj_admit_type in ('FRS','IPF','IFR') and ipeds_full_part_time = 'F' and wa_residency = 'NON-D'; 
 *tables uaa_flag*term_code UAA_flag*yr2_cont*term_code;
 *where adj_admit_type in ('FRS','IPF','IFR') and ipeds_full_part_time = 'F' and wa_residency = 'RES'; 
run;


data temp;
 set fresh_status8;
if HS_GPA10 not in ('g3.2 - 3.299','h3.3 - 3.399') then delete;
if admit_term1 not in (20073, 20083, 20093, 20103, 20113, 20123, 20133, 20143, 20153, 20163, 20173, 20183) then delete;
if UAA > 0 then UAA_flag = 1; else UAA_flag = 0;
if CAA > 0 then CAA_flag = 1; else CAA_flag = 0;
if WA_Residency ne 'NON-D' then delete;
proc freq;
 tables stated_unmet_need_acpt*term_code ipeds_minority_ind*term_code first_gen_flag*term_code wa_residency*term_code UAA_Flag*term_code;
 where adj_admit_type in ('FRS','IPF','IFR') and ipeds_full_part_time = 'F' and yr2_cont = 0; 
run; 

proc freq;
 tables perkins_rec*wa_residency  unsub_loan*term_code;
/* where fed_need > 10000;*/
run;



data temp;
 set fresh_status8;
If admit_term1 not in (20073, 20083, 20093, 20103, 20113, 20123, 20133, 20143, 20153, 20163,20173,20183) then delete; 
proc freq;
 tables stated_unmet_need_acpt*term_code;
/* where pell_eligibility_ind = 1;*/
 where first_gen_flag = 'Y';
run;



data temp;
 set fresh_status8;
if term_code ne 20153 then delete;
keep emplid term_code high_school_gpa degree_term_code yr2_cont yr3_cont final_gpa aid_year fed_need total_offer total_accept total_disb 
	 unmet_need_disb unmet_need_acpt
     stated_unmet_need_disb stated_unmet_need_acpt;
proc sort;
 by emplid;
run;


data temp;
 set fresh_status8;
if term_code ne '20153' then delete;
if UAA ne 1 then delete;
if HS_GPA ne 'd2.5 - 3.000'  then delete;
run;


** Beginning to optimize models;
** All together - 2nd yr retention;
*6018;
Data working;
 set fresh_status8;
If admit_term1 not in (20153, 20163,20173) then delete; 
If admit_term1 = 20153 then cohort = '3';
If admit_term1 = 20163 then cohort = '2';
If admit_term1 = 20173 then cohort = '1'; 
proc freq;
  tables stated_unmet_need3;
proc logistic  desc ;
 class  hs_gpa3  stated_unmet_need_acpt sex cohort first_gen_flag WA_residency ;
  Model  YR2_cont=  hs_gpa3 stated_unmet_need_acpt  sex first_gen_flag cohort wa_residency wa_residency*cohort stated_unmet_need_acpt*cohort/lackfit  ;
  where adj_admit_type in ('FRS','IFR','IPF');
  output out=yr2out predicted=estprop reschi=pearson resdev=deviance difdev=deletion;
run;





proc freq;
 tables Yr2_cont*stated_unmet_need/ chisq expected;
 *tables yr2_cont*need1/ chisq expected;
 *where ipeds_minority_ind = 1;
 *Where first_gen_flag = 'Y';
 by term_code;
run;


proc freq;
 tables stated_unmet_need*QValue_cat2;
 by term_code;
run;
proc freq;
 *Tables yr2_cont*HS_GPA1 yr3_cont*HS_GPA1 WSU_GPA*HS_GPA1 yr2_cont*Best_score yr2_cont*WSU_GPA yr3_cont*Best_score yr2_cont*deficient_eot_ind/  chisq expected;
 *Tables Yr2_cont*ipeds_minority_ind Yr2_cont*first_gen_flag Yr2_cont*Sex Yr2_cont*Best_score / chisq expected;
 
 data temp;
  set fresh_status8;
if term_code ne '20153' then delete;
if UAA ne 1 then delete;
keep emplid adj_admit_type UAA;
run;





*********************************  Creating Output File for Elias ****************************************************;
*15180 spring 2019;

proc sql;
 create table output as
 select distinct
 wsu_id,
 emplid,
 admit_term,
 adj_admit_type,
 adj_admit_campus,
 high_school_gpa,
 transfer_gpa,
 transfer_hours,
 qvalue,
 avalue,
 best,
 bestr,
 sat_i_comp,
 sat_i_math,
 sat_i_verb,
 sat_i_wr,
 act_comp,
 act_wr,
 sat_erws,
 sat_mss,
 age,
 case when ipeds_full_time_ind = 1 then 'F'
      when ipeds_full_time_ind = 0 then 'P' end as ipeds_full_part_time,
 ipeds_minority_ind,
 ipeds_ethnic_group,
 ipeds_ethnic_group_descr,
 WA_residency,
 first_gen_flag,
 pell_eligibility_ind,
 year,
 degree_term_code,
 yr1_grad,
 yr2_grad,
 yr3_grad,
 yr4_grad,
 yr5_grad,
 yr6_grad,
 yr7_grad,
 yr8_grad,
 yr9_grad,
 yr10_grad,
 yr11_grad,
 yr2_cont,
 yr3_cont,
 yr4_cont,
 yr5_cont,
 yr6_cont,
 yr7_cont,
 yr8_cont,
 yr9_cont,
 yr10_cont,
 yr11_cont,
 yr12_cont,
 yr2_not_enroll,
 yr3_not_enroll,
 yr4_not_enroll,
 yr5_not_enroll,
 yr6_not_enroll,
 yr7_not_enroll,
 yr8_not_enroll,
 yr9_not_enroll,
 yr10_not_enroll,
 yr11_not_enroll,
 yr12_not_enroll,
 first_year_success,
 degree_gpa,
 degree_ch,
 degree_transferch,
 sex,
 last_gpa,
 final_gpa,
 last_sch_attend as last_school_id,
 school_type as last_school_type1,
 ext_org_descr as last_school_attended,
 ext_org_city as last_school_city,
 ext_org_state as last_school_state,
 proprietorship,
 state_district_code,
 state_school_code,

 ext_degree_code,
 ext_degree_term_code,
 ext_degree_category_level_code,

 Total_Enrl,
 per_eligible_lunch,
 Masters,
 transfer_credit_adj_final,
 aid_year,

 fed_need_yr1,
 total_offer_yr1,
 total_accept_yr1,
 total_disb_yr1,
 UAA_yr1,
 CAA_yr1,
 State_need_yr1,
 cougar_comm_tot_yr1,
 crim_tran_tot_yr1,
 crim_tran_nr_yr1,

 fed_need_yr2,
 total_offer_yr2,
 total_accept_yr2,
 total_disb_yr2,
 UAA_yr2,
 CAA_yr2,
 State_need_yr2,
 cougar_comm_tot_yr2,
 crim_tran_tot_yr2,
 crim_tran_nr_yr2,

 fed_need_yr3,
 total_offer_yr3,
 total_accept_yr3,
 total_disb_yr3,
 UAA_yr3,
 CAA_yr3,
 State_need_yr3,
 cougar_comm_tot_yr3,
 crim_tran_tot_yr3,
 crim_tran_nr_yr3,

 fed_need_yr4,
 total_offer_yr4,
 total_accept_yr4,
 total_disb_yr4,
 UAA_yr4,
 CAA_yr4,
 State_need_yr4,
 cougar_comm_tot_yr4,
 crim_tran_tot_yr4,
 crim_tran_nr_yr4,

 fed_need_yr5,
 total_offer_yr5,
 total_accept_yr5,
 total_disb_yr5,
 UAA_yr5,
 CAA_yr5,
 State_need_yr5,
 cougar_comm_tot_yr5,
 crim_tran_tot_yr5,
 crim_tran_nr_yr5,

 fed_need_yr6,
 total_offer_yr6,
 total_accept_yr6,
 total_disb_yr6,
 UAA_yr6,
 CAA_yr6,
 State_need_yr6,
 cougar_comm_tot_yr6,
 crim_tran_tot_yr6,
 crim_tran_nr_yr6,

 graduate,
 WSU_GPA,
 HS_GPA1, 
 lunch ,
 best_score,
 bestr_score,
 qvalue_cat2,
 avalue_cat2,

 unmet_need_ofr_yr1,
 unmet_need_acpt_yr1,
 unmet_need_disb_yr1,
 stated_unmet_need_ofr_yr1,
 stated_unmet_need_acpt_yr1,
 stated_unmet_need_disb_yr1,

 unmet_need_ofr_yr2,
 unmet_need_acpt_yr2,
 unmet_need_disb_yr2,

 unmet_need_ofr_yr3,
 unmet_need_acpt_yr3,
 unmet_need_disb_yr3,

 unmet_need_ofr_yr4,
 unmet_need_acpt_yr4,
 unmet_need_disb_yr4,

 unmet_need_ofr_yr5,
 unmet_need_acpt_yr5,
 unmet_need_disb_yr5,

 unmet_need_ofr_yr6,
 unmet_need_acpt_yr6,
 unmet_need_disb_yr6


 from fresh_status8
 order by  emplid
 ;
 quit;

PROC EXPORT DATA=  output
			OUTFILE= "Z:\Student\Retention and Graduation\Student Retention & Graduation Predictive Models\VANCO_2197_census.xlsx"
			DBMS= xlsx REPLACE;
			sheet='Sheet1';
RUN;


run;
*checking;
data temp;
 set output;
if emplid ne '011417318' then delete;
run;


/*
proc freq;
tables  term_code*qvalue_cat2;
*  tables HS_GPA1*stated_unmet_need1;
* tables  term_code HS_GPA3*term_code qvalue_cat*term_code best_score*term_code first_gen_flag*term_code stated_unmet_need*term_code /norow nopercent  ;
* tables term_code*UAA;
* tables stated_unmet_need1;
 * To run within a Gpa group;
*ods graphics on;
Proc freq;
 Tables UAA CAA Regents Yr2_cont*Program Yr2_cont*UAA Yr2_cont*CAA Yr2_cont*Regents Yr3_cont*Program 
                Yr3_cont*UAA Yr3_cont*CAA Yr3_cont*Regents 
 				financial*Program financial*UAA financial*CAA financial*Regents/ chisq expected;
 *Tables UAA CAA Regents Regents StillEnrl5yr*UAA StillEnrl7yr*CAA StillEnrl7yr*Regents StillEnrl5yr*Program financial*Program 
                 financial*UAA financial*CAA financial*Regents/ chisq expected;
 *Tables UAA CAA Regents Regents StillEnrl6yr*UAA StillEnrl6yr*CAA StillEnrl6yr*Regents StillEnrl6yr*Program financial*Program
                 financial*UAA financial*CAA financial*Regents/ chisq expected;
 *Tables UAA CAA Regents StillEnrl7yr*UAA StillEnrl7yr*CAA StillEnrl7yr*Regents StillEnrl7yr*Program financial*Program 
                 financial*UAA financial*CAA financial*Regents / chisq expected;
 by term_code;
proc freq;
 Tables yr2_cont*HS_GPA yr3_cont*HS_GPA WSU_GPA*HS_GPA yr2_cont*Best_score yr3_cont*Best_score/ chisq expected;
 *Tables HS_GPA StillEnrl5yr*HS_GPA  WSU_GPA*HS_GPA StillEnrl5Yr*Best_score / chisq expected;
 *Tables HS_GPA StillEnrl6yr*HS_GPA  WSU_GPA*HS_GPA StillEnrl6Yr*Best_score/ chisq expected;
 *Tables  StillEnrl7yr*HS_GPA  WSU_GPA*HS_GPA  StillEnrl7Yr*Best_score Program*stated_unmet_need UAA CAA Regents/ chisq expected;
 by term_code;
 */
run;

** For Jocelyn's request:  Sophomore students who entered as first time freshmen fall 2013 with hs GPA of 3.6 or higher;
*989;
Data temp;
 set Fresh_status8;
if term_code ne '20133' then delete;
if adj_admit_campus ne 'PULLM' then delete;
if high_school_gpa lt 3.6 then delete;
admit_term = term_code;
keep emplid wsu_id admit_term adj_admit_type adj_admit_campus high_school_gpa;
run;

*1117;
Proc sql;
 create table sophomore_ha_fresh as
 select distinct 
 a.*,
 b.strm,
 b.first_name,
 b.middle_name,
 b.last_name,
 b.official_email_addr,
 b.preferred_email_addr
 from temp as a
 left join census.student_enrolled_vw as b
 on a.emplid = b.emplid 
 where b.strm in ('2143','2145')
 and b.snapshot in ('eot','ceneot')
 and b.ferpa = 'N'
 ;
quit;

*955;
data recruit;
 set sophomore_ha_fresh;
keep emplid wsu_id admit_term adj_admit_type adj_admit_campus high_school_gpa first_name middle_name last_name official_email_addr preferred_email_addr;
proc sort nodupkey;
 by emplid;
run;

*1117;
Proc sql;
 create table recruit1 as
 select distinct 
 a.*,
 b.full_address,
 b.strm
 from recruit as a
 left join census.student_address_MHPC_vw as b
 on a.emplid = b.emplid 
 where b.strm in ('2143','2145')
 and b.snapshot in ('eot','ceneot')
 ;
quit;

*955;
data recruit2;
 set recruit1;
proc sort;
 by emplid descending strm;
proc sort nodupkey;
 by emplid;
run;

*955;
proc sql;
 create table recruit_final as
 select distinct
 a.emplid,
 a.wsu_id,
 a.admit_term,
 a.adj_admit_type,
 a.adj_admit_campus,
 a.first_name,
 a.middle_name,
 a.last_name,
 a.official_email_addr,
 a.preferred_email_addr,
 a.full_address,
 b.acad_plan_descr
 from recruit2 as a
 left join census.student_acad_prog_plan_vw as b
 on a.emplid = b.emplid
 where b.strm = '2143' 
 and b.snapshot = 'eot'
 and b.primary_plan_flag = 'Y'
;
quit;




******************************************* Model Building **************************************************************;


** Beginning to optimize models;
** All together - 2nd yr retention;
*6018;
Data working;
 set fresh_status8;
 proc freq;
  tables stated_unmet_need3;
proc logistic  desc ;
 class  hs_gpa3 lunch   stated_unmet_need3;
 *class stated_unmet_need;
 *class hs_gpa qvalue_cat First_gen_flag;
 * Model  first_year_success = qvalue_cat pell_eligibility_ind First_gen_flag stated_unmet_need1;
  Model  YR2_cont= hs_gpa3  stated_unmet_need3 lunch  /lackfit  ;
  output out=yr2out predicted=estprop reschi=pearson resdev=deviance difdev=deletion;
  *Model  YR3_not_enroll= qvalue pell_eligibility_ind First_gen_flag  ; 
  *Model  FourYrGrad = qvalue  pell_eligibility_ind First_gen_flag ;
  *Model  FiveYrGrad = qvalue  pell_eligibility_ind First_gen_flag ;
 *Model  SixYrGrad= qvalue_cat2 stated_unmet_need/   lackfit ;
run;



** Beginning to optimize models;
** All together - 2nd yr retention;
*6018;
Data working;
 set fresh_status8;
if term_code not in (20073, 20083, 20093, 20103, 20113) then delete;
If unmet_need le 0  then stated_unmet_need3 =                        'z None        ';
If unmet_need ge 0 and unmet_need < 1000 then stated_unmet_need3 =                        'b< $1000      ';
If unmet_need ge 1000 and unmet_need lt 4000 then stated_unmet_need3 = 'c$1000 - $3999';
If unmet_need ge 4000 then stated_unmet_need3 = 'e > $4000   ';
If unmet_need = . then stated_unmet_need3 = 'z None        ';
 proc freq;
  tables stated_unmet_need3 stated_unmet_need3*yr3_cont stated_unmet_need3*term_code;
proc logistic  desc ;
 class  hs_gpa3 lunch   stated_unmet_need3;
 *class stated_unmet_need;
 *class hs_gpa qvalue_cat First_gen_flag;
 * Model  first_year_success = qvalue_cat pell_eligibility_ind First_gen_flag stated_unmet_need1;
  Model  YR3_cont= hs_gpa3  stated_unmet_need3 lunch  /lackfit  ;
  output out=yr2out predicted=estprop reschi=pearson resdev=deviance difdev=deletion;
  *Model  YR3_not_enroll= qvalue pell_eligibility_ind First_gen_flag  ; 
  *Model  FourYrGrad = qvalue  pell_eligibility_ind First_gen_flag ;
  *Model  FiveYrGrad = qvalue  pell_eligibility_ind First_gen_flag ;
 *Model  SixYrGrad= qvalue_cat2 stated_unmet_need/   lackfit ;
run;

*6018;
data temp;
 set yr2out;
proc sort;
 by pearson;
run;

*4437;
data working_yr2ret;
 set yr2out;
if pearson < -3 then delete;
proc logistic  desc ;
 class  stated_unmet_need1  lunch first_gen_flag  ;
  Model  YR2_cont= high_school_gpa stated_unmet_need1 lunch first_gen_flag f2009 f2010 f2011/lackfit  ;
  output out=yr2out2 reschi=pearson resdev=deviance difdev=deletion;
run;

data temp;
 set yr2out2;
proc sort;
 by pearson;
run;







** Highest GPA group;
** Problematic--this group has some high acheivers that leave;
*6018;
Data working;
 set fresh_status8;
proc logistic  desc ;
 class  stated_unmet_need1  lunch first_gen_flag  ;
 *class stated_unmet_need;
 *class hs_gpa qvalue_cat First_gen_flag;
 * Model  first_year_success = qvalue_cat pell_eligibility_ind First_gen_flag stated_unmet_need1;
  Model  YR2_cont= high_school_gpa  stated_unmet_need1 lunch first_gen_flag /lackfit  ;
  output out=yr2out reschi=pearson resdev=deviance difdev=deletion;
  *Model  YR3_not_enroll= qvalue pell_eligibility_ind First_gen_flag  ; 
  *Model  FourYrGrad = qvalue  pell_eligibility_ind First_gen_flag ;
  *Model  FiveYrGrad = qvalue  pell_eligibility_ind First_gen_flag ;
 *Model  SixYrGrad= qvalue_cat2 stated_unmet_need/   lackfit ;
run;

*6018;
data temp;
 set yr2out;
proc sort;
 by deviance;
run;

*4437;
data working_yr2ret;
 set yr2out;
if pearson < -3 then delete;
proc logistic  desc ;
 class  stated_unmet_need1  lunch first_gen_flag  ;
  Model  YR2_cont= high_school_gpa stated_unmet_need1 lunch first_gen_flag f2009 f2010 f2011/lackfit  ;
  output out=yr2out2 reschi=pearson resdev=deviance difdev=deletion;
run;

data temp;
 set yr2out2;
proc sort;
 by pearson;
run;


** Beginning to optimize models;
** Mid GPA group;
** Problematic--this group has some high acheivers that leave;
*6018;
Data working2;
 set fresh_status8;
proc logistic  desc ;
 class  stated_unmet_need1  lunch first_gen_flag   ;
 *class stated_unmet_need;
 *class hs_gpa qvalue_cat First_gen_flag;
 * Model  first_year_success = qvalue_cat pell_eligibility_ind First_gen_flag stated_unmet_need1;
  Model  YR2_cont= high_school_gpa  stated_unmet_need1 lunch first_gen_flag /lackfit  ;
  output out=yr2out  predicted=estprop reschi=pearson resdev=deviance difdev=deletion;
  *Model  YR3_not_enroll= qvalue pell_eligibility_ind First_gen_flag  ; 
  *Model  FourYrGrad = qvalue  pell_eligibility_ind First_gen_flag ;
  *Model  FiveYrGrad = qvalue  pell_eligibility_ind First_gen_flag ;
 *Model  SixYrGrad= qvalue_cat2 stated_unmet_need/   lackfit ;
run;

*6018;
data temp;
 set yr2out;
proc sort;
 by deviance;
run;

*4437;
data working_yr2ret;
 set yr2out;
if pearson < -3 then delete;
proc logistic  desc ;
 class  stated_unmet_need1  lunch first_gen_flag  ;
  Model  YR2_cont= high_school_gpa stated_unmet_need1 lunch first_gen_flag f2009 f2010 f2011/lackfit  ;
  output out=yr2out2 predicted=estprop reschi=pearson resdev=deviance difdev=deletion;
run;

data temp;
 set yr2out2;
proc sort;
 by pearson;
run;















