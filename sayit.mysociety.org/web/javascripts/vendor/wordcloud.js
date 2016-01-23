$(function () {

  // Word cloud
  if ($('.wordcloud').length) {
	// @see http://www.jasondavies.com/wordcloud/cloud.js
	var fill = d3.scale.category20b()
	, cloud = $('.wordcloud')
	, w = cloud.width()
	, h = cloud.height()
	, font = '"Helvetica Neue", Helvetica, sans serif';

	var fontSize = d3.scale.log().range([10, 100]).domain([
	  d3.min(most_common_words, function(d) { return d[1]; })
	, d3.max(most_common_words, function(d) { return d[1]; })
	]);

	d3.layout.cloud()
	  .words($.map(most_common_words, function (d) {
		return {
		  text: d[0]
		, score: d[1]
		}
	  }))
	  .timeInterval(10)
	  .size([w, h])
	  .rotate(0)
	  .font(font)
	  .fontWeight("bold")
	  .fontSize(function (d) { return fontSize(+d.score); })
	  .text(function(d) { return d.text; })
	  .on("end", function (words, bounds) {
		d3.select(".wordcloud")
		  .append("svg")
			.attr("width", w)
			.attr("height", h)
		  .append("g")
			.attr("transform", "translate(" + [w >> 1, h >> 1] + ")")
		  .selectAll("text")
			.data(words)
			.enter()
		  .append("text")
			.attr("class", "cloud-word")
			.attr("text-anchor", "middle")
			.attr("transform", function(d) { return "translate(" + [d.x, d.y] + ")"; })
			.style("font-family", font)
			.style("font-weight", "bold")
			.style("font-size", function(d) { return d.size + "px"; })
			.style("fill", function(d, i) { return fill(i); })
			.text(function(d) { return d.text; })
			.on("click", function (d) {
			  window.location = '/search/?q=' + d.text;
			});
	  })
	  .start();
  }
});
