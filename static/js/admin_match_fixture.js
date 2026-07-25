/** Filter Home/Away team dropdowns by the selected Competition Group. */
(function ($) {
  $(function () {
    var $group = $("#id_group");
    var $home = $("#id_home_team");
    var $away = $("#id_away_team");
    if (!$group.length || !$home.length || !$away.length) {
      return;
    }

    var teamsUrl = $group.attr("data-teams-url");
    if (!teamsUrl) {
      return;
    }

    function setOptions($select, teams, selected, emptyLabel) {
      var previous = selected;
      $select.empty();
      $select.append(
        $("<option></option>")
          .attr("value", "")
          .text(emptyLabel || "---------")
      );
      (teams || []).forEach(function (name) {
        $select.append($("<option></option>").attr("value", name).text(name));
      });
      if (previous && teams && teams.indexOf(previous) !== -1) {
        $select.val(previous);
      } else {
        $select.val("");
      }
    }

    function loadTeams(keepSelection) {
      var groupId = $group.val();
      var keepHome = keepSelection ? $home.val() : null;
      var keepAway = keepSelection ? $away.val() : null;

      if (!groupId) {
        setOptions($home, [], null, "--------- Select a group first ---------");
        setOptions($away, [], null, "--------- Select a group first ---------");
        return;
      }

      $.getJSON(teamsUrl, { group_id: groupId })
        .done(function (data) {
          var teams = data.teams || [];
          setOptions($home, teams, keepHome, "---------");
          setOptions($away, teams, keepAway, "---------");
        })
        .fail(function () {
          setOptions($home, [], null, "---------");
          setOptions($away, [], null, "---------");
        });
    }

    $group.on("change", function () {
      loadTeams(false);
    });

    // Refresh options when editing / after validation errors with a group set.
    if ($group.val()) {
      loadTeams(true);
    }
  });
})(django.jQuery);
