import { Component, OnInit } from '@angular/core';
import { DataService } from '../../services';
import { routesConsts } from '../../consts';
import {Router} from "@angular/router";
import {environment} from "../../../environments/environment";

@Component({
  selector: 'app-header-mobile',
  templateUrl: './header.component.mobile.html',
  styleUrls: ['./header.component.mobile.css']
})
export class HeaderComponentMobile implements OnInit {

  isMainnet: boolean = false;
  isMasternet: boolean = false;

  searchControls = {
    searchElem: "../../../assets/iconSearch.png",
    searchDeclineElem: "../../../assets/iconDeclineSearch.png"
  };
  isSearchInputVisible = false;

  activeSearchControl = this.searchControls.searchElem;

  constructor(private dataService: DataService, private router: Router) {}

  ngOnInit() {
    this.isMasternet = environment.masternet;
    this.isMainnet = environment.production;
  }

  searchClicked() {
    this.isSearchInputVisible = !this.isSearchInputVisible;
    this.activeSearchControl = this.activeSearchControl == this.searchControls.searchElem ?
      this.searchControls.searchDeclineElem : this.searchControls.searchElem;
  }

  navigateToHomepage(){
      this.router.navigate(
          [routesConsts.HOME]
      );
  }

  searchProcess(input) {
      let searchValue = input.value;
      input.value = '';
      this.dataService.searchBlock(searchValue).subscribe((blockItem) => {
        if (blockItem.found !== undefined && !blockItem.found) {
          this.router.navigate(
            [routesConsts.BLOCK_NOT_FOUND]
          );
        } else if (blockItem.hash !== undefined){
          this.router.navigate(
            [routesConsts.BLOCK_DETAILS, blockItem.hash],
            {queryParams: {searched_by: searchValue}}
          );
        }
      }, (error) => {
          this.router.navigate(
              [routesConsts.BLOCK_NOT_FOUND]
          );
      });
  }
}
