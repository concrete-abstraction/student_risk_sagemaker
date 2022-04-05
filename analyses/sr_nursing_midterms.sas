%macro loop();

	%do var=2017 %to 2022 %by 1;
	
		proc sql;
			create table work.query_&var. as
			select strm , emplid , class_nbr , crse_id , subject_catalog_nbr , unt_taken , spring_midterm_grade , spring_midterm_grade_ind , spring_midterm_s_grade_ind , spring_midterm_x_grade_ind , spring_midterm_z_grade_ind , spring_midterm_w_grade_ind from work.spring_midterm_&var. where subject_catalog_nbr like ('%NURS%') and spring_midterm_grade = . order by sortkey(subject_catalog_nbr, "EN_US");
		quit;
		
		proc datasets nolist nodetails;
			contents data=work.query_&var. out=work.details_&var.;
		run;
		
		proc print data=work.details_&var.;
		run;
		
		proc freq data=query_&var.;
			table subject_catalog_nbr;
		run;
		
	%end;
	
%mend loop;

%loop;
