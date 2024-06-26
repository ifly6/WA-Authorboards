# WA Authorboards #

WA Authorboards is forked from Auralia's [nswadb](https://github.com/auralia/nswadb). It is free and open source. There is—

* a CSV database containing information on all General Assembly resolutions;

* Python scripts that generate a bbCode list of General Assembly resolutions by author, as well as a number of associated bbCode tables containing statistical information;

* parsing code to poll the NS API to generate an updated version of that database, along with code necessary to properly capitalise names, categories, etc; **You should check automated parser output for errors**;

* code to generate tables, tally votes, etc for the GA Annual Review; and

* code to generate a hypothetical sunset queue.

## Contributions ##

If you find an error in this database, please don't complain and badger me about it to me in Discord, telegrams, or some chat. [Go and fork the repository, fix it yourself, and suggest the changes via pull request](https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/creating-a-pull-request-from-a-fork). This way, the fix gets implemented and you also get credit for the fix.

The output tables in `md_output` are **not** the raw data. As the name implies, files in that folder are generated by scripts in Markdown format. The actual source data that needs updating is in the `db` folder. Errors in the `md_output` table will be corrected when the output cache is regenerated. If you want to update those tables directly, run the script yourself after forking the repository.

Otherwise, this respository gets updated whenver I feel like it. If you want something updated on your schedule, do it yourself. This is on GitHub, rather than hosted on something like my [personal site](https://ifly6.no-ip.org), for the sole purpose of allowing you to suggest and make your own changes. Embrace that teleology. 

## Licence ##

This project is licensed under the [Apache License 2.0](http://www.apache.org/licenses/LICENSE-2.0). A large number of files herein have been modified from Auralia's source. Modification copyright 2021 ifly6. Other modification copyrights property of their owners.

The outputs in this respository in the `md_output` folder, which I generated, are not licenced under the Apache Licence. I reserve all rights thereto.
