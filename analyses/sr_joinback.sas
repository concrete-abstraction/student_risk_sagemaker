option validvarname=V7;

proc import out=testing_set
          	datafile="Z:\Nathan\Models\student_risk\analyses\testing_set.xlsx" 
            dbms=xlsx replace;
     getnames=yes;
run;

data testing_set;
	set testing_set;
	student_id = put(emplid, z9.);
run;

option validvarname=V7;

proc import out=overview
          	datafile="Z:\Nathan\Models\student_risk\analyses\student_risk_overview.xlsx" 
            dbms=xlsx replace;
     getnames=yes;
run;

proc sort data=overview nodupkey dupout=overview_dups;
	by student_id;
run;

proc sql;
	create table joined as 
	select a.*
		,b.*
	from testing_set as a
	left join overview as b
		on a.student_id = b.student_id
;quit;