/**
 * Filter Home/Away team dropdowns by the selected Competition Group.
 *
 * Must tolerate loading before admin/js/jquery.init.js defines django.jQuery
 * (Django inserts ModelAdmin.Media scripts between jquery.js and jquery.init.js).
 */
(function () {
  function init($) {
    var $group = $("#id_group");
    var $home = $("#id_home_team");
    var $away = $("#id_away_team");
    if (!$group.length || !$home.length || !$away.length) {
      return;
    }

    var teamsUrl =
      $group.attr("data-teams-url") ||
      window.GFC_MATCH_TEAMS_URL ||
      "/admin/club/match/teams-for-group/";

    function setOptions($select, teams, selected, emptyLabel) {
      $select.empty();
      $select.append(
        $("<option></option>")
          .attr("value", "")
          .text(emptyLabel || "---------")
      );
      (teams || []).forEach(function (name) {
        $select.append($("<option></option>").attr("value", name).text(name));
      });
      if (selected && teams && teams.indexOf(selected) !== -1) {
        $select.val(selected);
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
          if (!teams.length) {
            setOptions(
              $home,
              [],
              null,
              "--------- No teams in this group yet ---------"
            );
            setOptions(
              $away,
              [],
              null,
              "--------- No teams in this group yet ---------"
            );
            return;
          }
          setOptions($home, teams, keepHome, "---------");
          setOptions($away, teams, keepAway, "---------");
        })
        .fail(function () {
          setOptions(
            $home,
            [],
            null,
            "--------- Could not load teams — refresh and try again ---------"
          );
          setOptions(
            $away,
            [],
            null,
            "--------- Could not load teams — refresh and try again ---------"
          );
        });
    }

    // Delegate so it still works if the widget is re-rendered.
    $(document).on("change", "#id_group", function () {
      loadTeams(false);
    });

    if ($group.val()) {
      loadTeams(true);
    }
  }

  function waitForDjangoJQuery(attempts) {
    attempts = attempts || 0;
    if (window.django && django.jQuery) {
      init(django.jQuery);
      return;
    }
    if (attempts < 60) {
      window.setTimeout(function () {
        waitForDjangoJQuery(attempts + 1);
      }, 50);
    }
  }

  waitForDjangoJQuery(0);
})();
