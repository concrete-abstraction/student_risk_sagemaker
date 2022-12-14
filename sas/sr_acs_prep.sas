options nosyntaxcheck;

libname acs "Z:\Nathan\Models\student_risk\supplemental_files";

%let start_year = 2019;
%let end_year = 2020;

/* Define character to numeric macro */

%macro char2num(inputlib=acs, /* Pre-define libref for input data set */
				inputdsn=, /* Pass in name of input data set in macro call */
				outputlib=acs, /* Pre-define libref for output data set */
				outputdsn=, /* Pass in name of output data set in macro call */
				excludevars=); /* Pass in variable names to exclude in macro call */

	proc sql noprint;
		select name into: charvars separated by ' '	
		from dictionary.columns
		where libname=upcase("&inputlib") 
			and memname=upcase("&inputdsn") 
			and type="char"
	 		and not indexw(upcase("&excludevars"), upcase(name));
	;quit;
	
	%let ncharvars=%sysfunc(countw(&charvars));

	data _null_;
		set &inputlib..&inputdsn end=lastobs;
		array charvars{*} &charvars;
		array charvals{&ncharvars};

		do i=1 to &ncharvars;
 			if input(charvars{i},?? best12.)=. and charvars{i} ne ' ' then charvals{i}+1;
		end;

		if lastobs then do;
 			length varlist $ 32767;
 			
 			do j=1 to &ncharvars;
				if charvals{j}=. then varlist=catx(' ',varlist,vname(charvars{j}));
			end;
 
 			call symputx('varlist',varlist);
		end;
	run;

	%let nvars=%sysfunc(countw(&varlist));

	data temp;
		set &inputlib..&inputdsn;
		array charx{&nvars} &varlist;
		array x{&nvars} ;

		do i=1 to &nvars;
			x{i}=input(charx{i},best12.);
		end;

		drop &varlist i;
		
		%do i=1 %to &nvars;
 			rename x&i = %scan(&varlist,&i) ;
		%end;
	run;
	
	proc sql noprint;
		select name into :orderlist separated by ' '
		from dictionary.columns
		where libname=upcase("&inputlib") 
			and memname=upcase("&inputdsn")
		order by varnum;
		
		select catx(' ','label',name,'=',quote(trim(label)),';')
 			into :labels separated by ' '
		from dictionary.columns
		where libname=upcase("&inputlib") 
			and memname=upcase("&inputdsn") 
			and indexw(upcase("&varlist"),upcase(name))
	;quit;

	data &outputlib..&outputdsn;
		retain &orderlist;
		set temp;
		&labels;
	run;
		
%mend char2num; 

/* Define loop macro for processing ACS data */

%macro loop;
	
	%do year=&start_year. %to &end_year.;
		
	/* Demographic data */
	proc import out=acs_demo_&year. (keep=geoid B01001e1)
		datafile="C:\Users\nathan.lindstedt\Desktop\acs_raw\acs_&year._5yr_zcta_X01_AGE_AND_SEX.csv"
		dbms=CSV REPLACE;
		getnames=YES;
		guessingrows=100;
	run;
	
	proc sql;
		create table acs.acs_demo_&year. as
		select
			substr(geoid, 8, 5) as geoid
			,B01001e1 as pop
		from acs_demo_&year.
	;quit;
	
	%char2num(inputdsn=acs_demo_&year., outputdsn=acs_demo_&year., excludevars=geoid);
	
	/* Area data */
	proc import out=acs_area_&year. (keep=geoid_data aland10)
		datafile="C:\Users\nathan.lindstedt\Desktop\acs_raw\acs_&year._5yr_zcta_ACS_&year._5YR_ZCTA.csv"
		dbms=CSV REPLACE;
		getnames=YES;
		guessingrows=100;
	run;
	
	proc sql;
		create table acs.acs_area_&year. as
		select
			substr(geoid_data, 8, 5) as geoid
			,aland10 as area
		from acs_area_&year.
	;quit;
	
	%char2num(inputdsn=acs_area_&year., outputdsn=acs_area_&year., excludevars=geoid);
	
	/* Poverty data */
	proc import out=acs_poverty_&year. (keep=geoid B17001e1 B17001e2)
		datafile="C:\Users\nathan.lindstedt\Desktop\acs_raw\acs_&year._5yr_zcta_X17_POVERTY.csv"
		dbms=CSV REPLACE;
		getnames=YES;
		guessingrows=100;
	run;
	
	proc sql;
		create table acs.acs_poverty_&year. as
		select
			substr(geoid, 8, 5) as geoid
			,B17001e1 as pvrt_base
			,B17001e2 as pvrt_total
		from acs_poverty_&year.
	;quit;
	
	%char2num(inputdsn=acs_poverty_&year., outputdsn=acs_poverty_&year., excludevars=geoid);
	
	/* Income data */
	proc import out=acs_income_&year. (keep=geoid B19013e1 B19083e1)
		datafile="C:\Users\nathan.lindstedt\Desktop\acs_raw\acs_&year._5yr_zcta_X19_INCOME.csv"
		dbms=CSV REPLACE;
		getnames=YES;
		guessingrows=100;
	run;
	
	proc sql;
		create table acs.acs_income_&year. as
		select
			substr(geoid, 8, 5) as geoid
			,B19013e1 as median_inc
			,B19083e1 as gini_indx
		from acs_income_&year.
	;quit;
	
	%char2num(inputdsn=acs_income_&year., outputdsn=acs_income_&year., excludevars=geoid);
	
	/* Housing data */
	proc import out=acs_housing_&year. (keep=geoid B25077e1)
		datafile="C:\Users\nathan.lindstedt\Desktop\acs_raw\acs_&year._5yr_zcta_X25_HOUSING_CHARACTERISTICS.csv"
		dbms=CSV REPLACE;
		getnames=YES;
		guessingrows=100;
	run;
	
	proc sql;
		create table acs.acs_housing_&year. as
		select
			substr(geoid, 8, 5) as geoid
			,B25077e1 as median_value
		from acs_housing_&year.
	;quit;

	%char2num(inputdsn=acs_housing_&year., outputdsn=acs_housing_&year., excludevars=geoid);
	
	/* Education data */
	proc import out=acs_education_&year. (keep=geoid B15002e1 B15012e1)
		datafile="C:\Users\nathan.lindstedt\Desktop\acs_raw\acs_&year._5yr_zcta_X15_EDUCATIONAL_ATTAINMENT.csv"
		dbms=CSV REPLACE;
		getnames=YES;
		guessingrows=100;
	run;
	
	proc sql;
		create table acs.acs_education_&year. as
		select
			substr(geoid, 8, 5) as geoid
			,B15002e1 as educ_base
			,B15012e1 as educ_total
			,(B15012e1 / B15002e1) as educ_rate 
		from acs_education_&year.
	;quit;
	
	%char2num(inputdsn=acs_education_&year., outputdsn=acs_education_&year., excludevars=geoid);
	
	/* Race data */
	proc import out=acs_race_&year. (keep=geoid B02001e1 B02001e3 B02001e4 B02001e5 B02001e6 B02001e7 B02001e8)
		datafile="C:\Users\nathan.lindstedt\Desktop\acs_raw\acs_&year._5yr_zcta_X02_RACE.csv"
		dbms=CSV REPLACE;
		getnames=YES;
		guessingrows=100;
	run;
	
	proc sql;
		create table acs.acs_race_&year. as
		select
			substr(geoid, 8, 5) as geoid
			,B02001e1 as race_tot
			,B02001e3 as race_blk
			,B02001e4 as race_ai
			,B02001e5 as race_asn
			,B02001e6 as race_hawi
			,B02001e7 as race_oth
			,B02001e8 as race_two
		from acs_race_&year.
	;quit;
	
	%char2num(inputdsn=acs_race_&year., outputdsn=acs_race_&year., excludevars=geoid);
	
	/* Ethnicity data */
	proc import out=acs_ethnicity_&year. (keep=geoid B03001e1 B03001e3)
		datafile="C:\Users\nathan.lindstedt\Desktop\acs_raw\acs_&year._5yr_zcta_X03_HISPANIC_OR_LATINO_ORIGIN.csv"
		dbms=CSV REPLACE;
		getnames=YES;
		guessingrows=100;
	run;
	
	proc sql;
		create table acs.acs_ethnicity_&year. as
		select
			substr(geoid, 8, 5) as geoid
			,B03001e1 as ethnic_tot
			,B03001e3 as ethnic_hisp
		from acs_ethnicity_&year.
	;quit;
	
	%char2num(inputdsn=acs_ethnicity_&year., outputdsn=acs_ethnicity_&year., excludevars=geoid);
	
	%end;
	
%mend loop;

%loop;

%macro educ_loop;
	
	%do year=&start_year. %to &end_year.;
	
	/* Education data */
	proc import out=acs_education_&year. (keep=geoid B15002e1 B15012e1)
		datafile="C:\Users\nathan.lindstedt\Desktop\acs_raw\acs_&year._5yr_zcta_X15_EDUCATIONAL_ATTAINMENT.csv"
		dbms=CSV REPLACE;
		getnames=YES;
		guessingrows=2000;
	run;
	
	proc sql;
		create table acs.acs_education_&year. as
		select
			substr(geoid, 8, 5) as geoid
			,B15002e1 as educ_base
			,B15012e1 as educ_total
			,(B15012e1 / B15002e1) as educ_rate 
		from acs_education_&year.
	;quit;
	
	%end;
	
%mend educ_loop;

%educ_loop;
