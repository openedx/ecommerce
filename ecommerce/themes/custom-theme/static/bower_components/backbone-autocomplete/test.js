/*
<link rel="stylesheet" type="text/css" href="http://www.planbox.com/html/widgets/jquery.backbone.widgets.css"/>
<script src="http://www.planbox.com/html/widgets/3rd-party/jquery.min.js" type="text/javascript"></script>
<script src="http://www.planbox.com/html/widgets/3rd-party/underscore.js" type="text/javascript"></script>
<script src="http://www.planbox.com/html/widgets/3rd-party/backbone.js" type="text/javascript"></script>
<script src="http://www.planbox.com/html/widgets/jquery.backbone.widgets.js" type="text/javascript"></script>
<script src="http://www.planbox.com/html/widgets/test.js" type="text/javascript"></script>
<strong>Type in a State or Province</strong>
<input id="states_provinces" />
*/
$(document).ready(function() {
	var collection = new Backbone.Collection([
		{id:"AB", name:"Alberta"},
		{id:"BC", name:"British Columbia"},
		{id:"MB", name:"Manitoba"},
		{id:"NB", name:"New Brunswick"},
		{id:"NL", name:"Newfoundland and Labrador"},
		{id:"NT", name:"Northwest Territories"},
		{id:"NS", name:"Nova Scotia"},
		{id:"NU", name:"Nunavut"},
		{id:"ON", name:"Ontario"},
		{id:"PE", name:"Prince Edward Island"},
		{id:"QC", name:"Quebec"},
		{id:"SK", name:"Saskatchewan"},
		{id:"YT", name:"Yukon"},
		{id:"AL", name:"Alabama"},
		{id:"AK", name:"Alaska"},
		{id:"AS", name:"American Samoa"},
		{id:"AZ", name:"Arizona"},
		{id:"AR", name:"Arkansas"},
		{id:"CA", name:"California"},
		{id:"CO", name:"Colorado"},
		{id:"CT", name:"Connecticut"},
		{id:"DE", name:"Delaware"},
		{id:"DC", name:"District of Columbia"},
		{id:"FM", name:"Federated States of Micronesia"},
		{id:"FL", name:"Florida"},
		{id:"GA", name:"Georgia"},
		{id:"GU", name:"Guam"},
		{id:"HI", name:"Hawaii"},
		{id:"ID", name:"Idaho"},
		{id:"IL", name:"Illinois"},
		{id:"IN", name:"Indiana"},
		{id:"IA", name:"Iowa"},
		{id:"KS", name:"Kansas"},
		{id:"KY", name:"Kentucky"},
		{id:"LA", name:"Louisiana"},
		{id:"ME", name:"Maine"},
		{id:"MH", name:"Marshall Islands"},
		{id:"MD", name:"Maryland"},
		{id:"MA", name:"Massachusetts"},
		{id:"MI", name:"Michigan"},
		{id:"MN", name:"Minnesota"},
		{id:"MS", name:"Mississippi"},
		{id:"MO", name:"Missouri"},
		{id:"MT", name:"Montana"},
		{id:"NE", name:"Nebraska"},
		{id:"NV", name:"Nevada"},
		{id:"NH", name:"New Hampshire"},
		{id:"NJ", name:"New Jersey"},
		{id:"NM", name:"New Mexico"},
		{id:"NY", name:"New York"},
		{id:"NC", name:"North Carolina"},
		{id:"ND", name:"North Dakota"},
		{id:"MP", name:"Northern Mariana Islands"},
		{id:"OH", name:"Ohio"},
		{id:"OK", name:"Oklahoma"},
		{id:"OR", name:"Oregon"},
		{id:"PW", name:"Palau"},
		{id:"PA", name:"Pennsylvania"},
		{id:"PR", name:"Puerto Rico"},
		{id:"RI", name:"Rhode Island"},
		{id:"SC", name:"South Carolina"},
		{id:"SD", name:"South Dakota"},
		{id:"TN", name:"Tennessee"},
		{id:"TX", name:"Texas"},
		{id:"UT", name:"Utah"},
		{id:"VT", name:"Vermont"},
		{id:"VI", name:"Virgin Islands"},
		{id:"VA", name:"Virginia"},
		{id:"WA", name:"Washington"},
		{id:"WV", name:"West Virginia"},
		{id:"WI", name:"Wisconsin"},
		{id:"WY", name:"Wyoming"},
		{id:"AA", name:"Armed Forces Americas"},
		{id:"AE", name:"Armed Forces"},
		{id:"AP", name:"Armed Forces Pacific"}
	]);
	
	$('#states_provinces').autocomplete({
		collection: collection,
		attr: 'name',
		noCase: true,
		ul_class: 'autocomplete shadow',
		ul_css: {'z-index':1234},
    max_results: 5
	});
});
